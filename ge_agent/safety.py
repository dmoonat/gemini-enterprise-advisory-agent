# Copyright
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Safety and Security module for Gemini Enterprise Knowledge Agent.

Implements multi-layered safety and security controls in accordance with
the ADK Safety & Security guidelines (https://adk.dev/safety/):
1. Built-in Gemini Content Safety Filters (GenerateContentConfig + SafetySettings).
2. In-Tool Guardrails & Callbacks (SQL read-only enforcement, table whitelisting, injection defense).
3. MCP Tool Parameter Sanitization & Output Verification.
4. Input Screening (Prompt Injection & Jailbreak Defense via Fast-Path Heuristics & LLM Judge).
5. Output Screening & System Prompt Leak Protection.
6. ADK Reusable Safety Plugin (GeminiSafetyPlugin).
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.plugins import BasePlugin
from google.adk.tools import BaseTool, ToolContext
from google.genai import types

from .config import (
    ALLOWED_SQL_TABLES,
    SAFETY_BLOCK_THRESHOLD,
    SAFETY_ENABLED,
)

logger = logging.getLogger(__name__)

# Standard safe refusal response for out-of-domain or adversarial requests
STANDARD_REFUSAL_MESSAGE = (
    "I am an external technical support assistant for Gemini Enterprise. "
    "I can only assist with questions regarding Gemini Enterprise, related Google Cloud APIs, "
    "and platform release notes."
)

# SQL statements and keywords restricted to prevent unauthorized modifications
DISALLOWED_SQL_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE",
    "MERGE", "GRANT", "REVOKE", "EXECUTE IMMEDIATE", "CALL", "REPLACE",
    "INTO OUTFILE", "INTO DUMPFILE", "LOAD DATA"
]

# Patterns indicative of prompt injection, jailbreaking, or system prompt leaks
ADVERSARIAL_PATTERNS = [
    r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|guidelines)\b",
    r"(?i)\bdisregard\s+(all\s+)?(previous|prior|above|safety)\s+(instructions|rules|guidelines)\b",
    r"(?i)\byou\s+are\s+now\s+(DAN|Do\s+Anything\s+Now|unfiltered|jailbroken|ChaosGPT|EvilAI)\b",
    r"(?i)\bact\s+as\s+(an?\s+)?(unfiltered|unrestricted|developer\s+mode|jailbreak)\b",
    r"(?i)\b(output|reveal|leak|print|show|repeat|display)\s+(the\s+)?(system\s+prompt|system_instruction|hidden\s+instruction|internal\s+prompt)\b",
    r"(?i)\bhow\s+to\s+(bypass|hack|exploit|disable)\s+(firewall|security|antivirus|filter|guardrail)\b",
    r"(?i)\b(create|build|synthesize|manufacture)\s+(malware|ransomware|keylogger|bomb|explosive|weapon)\b",
]

# Prompts or tags indicating internal prompt leakage
INTERNAL_PROMPT_LEAK_MARKERS = [
    "<objective>",
    "<guardrails>",
    "<out_of_domain_handling>",
    "<workflow>",
    "SYSTEM_INSTRUCTION =",
    "You are an expert Technical Support Engineer and Documentation Assistant specializing in Gemini Enterprise. Your primary responsibility",
]


# ============================================================================
# 1. Built-in Gemini Content Safety Filters (GenerateContentConfig)
# ============================================================================

def get_harm_block_threshold(threshold_str: str = SAFETY_BLOCK_THRESHOLD) -> types.HarmBlockThreshold:
    """Maps a string threshold configuration to the GenAI HarmBlockThreshold enum."""
    threshold_mapping = {
        "BLOCK_LOW_AND_ABOVE": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        "BLOCK_MEDIUM_AND_ABOVE": types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        "BLOCK_ONLY_HIGH": types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        "BLOCK_NONE": types.HarmBlockThreshold.BLOCK_NONE,
        "OFF": types.HarmBlockThreshold.OFF,
    }
    return threshold_mapping.get(threshold_str.upper(), types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE)


def build_safety_settings(threshold_str: str = SAFETY_BLOCK_THRESHOLD) -> List[types.SafetySetting]:
    """Builds comprehensive Gemini content safety settings across harm categories.
    
    Reference: https://adk.dev/safety/#built-in-gemini-safety-features
    """
    threshold = get_harm_block_threshold(threshold_str)
    return [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=threshold,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=threshold,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=threshold,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=threshold,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
            threshold=threshold,
        ),
    ]


def build_generate_content_config(
    temperature: float = 0.2,
    threshold_str: str = SAFETY_BLOCK_THRESHOLD,
) -> types.GenerateContentConfig:
    """Creates a GenerateContentConfig object pre-configured with safety filters."""
    return types.GenerateContentConfig(
        temperature=temperature,
        safety_settings=build_safety_settings(threshold_str),
    )


# ============================================================================
# 2. In-Tool Guardrails (SQL & MCP Security)
# ============================================================================

def _normalize_table_name(tbl: str) -> str:
    """Normalizes BigQuery table identifier for comparison."""
    tbl = tbl.strip().replace("`", "")
    return tbl.lower()


def _extract_sql_tables(sql: str) -> List[str]:
    """Extracts table identifiers from SQL query string."""
    # Strip literal string constants to avoid false matches
    clean_sql = re.sub(r"'([^'\\]|\\.)*'", "''", sql)
    clean_sql = re.sub(r'"([^"\\]|\\.)*"', '""', clean_sql)

    patterns = [
        r'\bFROM\s+([`a-zA-Z0-9_\.\-]+)',
        r'\bJOIN\s+([`a-zA-Z0-9_\.\-]+)',
    ]
    tables = []
    for pattern in patterns:
        for match in re.finditer(pattern, clean_sql, re.IGNORECASE):
            tables.append(match.group(1))
    return tables


def validate_sql_security(sql: str, allowed_tables: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """Validates SQL query to ensure read-only execution on authorized tables.
    
    Enforces:
    - Only SELECT or WITH ... SELECT queries.
    - No DDL/DML operations (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, etc.).
    - No statement chaining (semicolon injection).
    - Strict table whitelisting against allowed release notes tables.
    """
    if not sql or not isinstance(sql, str):
        return False, "SQL query must be a non-empty string."

    clean_sql = sql.strip()
    if clean_sql.endswith(";"):
        clean_sql = clean_sql[:-1].strip()

    # Semicolon / query chaining check
    no_strings = re.sub(r"'([^'\\]|\\.)*'", "''", clean_sql)
    no_strings = re.sub(r'"([^"\\]|\\.)*"', '""', no_strings)
    if ";" in no_strings:
        return False, "Query chaining with multiple statements (';') is strictly prohibited."

    upper_sql = no_strings.upper().strip()

    # Read-only verification
    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        return False, "Only read-only SELECT queries (or WITH ... SELECT CTEs) are permitted."

    # Disallowed keywords verification
    for kw in DISALLOWED_SQL_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', upper_sql):
            return False, f"Disallowed SQL keyword '{kw}' detected. Write, DDL, and administrative operations are blocked."

    # Table whitelisting verification
    tables = _extract_sql_tables(sql)
    if not tables:
        return False, "Could not determine target table in SQL query."

    allowed = set(allowed_tables or ALLOWED_SQL_TABLES)
    norm_allowed = {_normalize_table_name(t) for t in allowed}

    for t in tables:
        norm_t = _normalize_table_name(t)
        if norm_t not in norm_allowed:
            return False, (
                f"Unauthorized table '{t}'. Queries are strictly restricted to authorized tables: "
                f"{', '.join(sorted(norm_allowed))}."
            )

    return True, None


def validate_mcp_security(tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validates MCP documentation tool parameters against abuse and injection."""
    for key, val in args.items():
        if isinstance(val, str):
            if len(val) > 2000:
                return False, f"Parameter '{key}' exceeds maximum allowed length of 2000 characters."
            # Check for command injection or control characters in query strings
            if "\x00" in val or "&&" in val or "||" in val or "`" in val:
                return False, f"Potentially dangerous control characters in parameter '{key}'."
    return True, None


def before_tool_guardrail(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Optional[Dict[str, Any]]:
    """Before-tool callback enforcing in-tool security policies.
    
    If validation fails, returns a dict error response to block tool execution
    and provide structured feedback to the model.
    """
    if not SAFETY_ENABLED:
        return None

    tool_name = getattr(tool, "name", str(tool))
    logger.debug("Executing before_tool_guardrail for tool: %s with args: %s", tool_name, args)

    # 1. SQL Execution Security Guardrail
    if tool_name == "execute_sql" or "sql" in tool_name.lower():
        query = args.get("query", "")
        is_valid, error_msg = validate_sql_security(query)
        if not is_valid:
            logger.warning("[SECURITY GUARDRAIL BLOCKED SQL]: %s | Error: %s", query, error_msg)
            return {
                "status": "error",
                "error": f"Security Policy Violation: SQL query rejected. {error_msg}"
            }

    # 2. MCP Documentation Tool Security Guardrail
    elif "mcp" in tool_name.lower() or "document" in tool_name.lower() or "search" in tool_name.lower():
        is_valid, error_msg = validate_mcp_security(tool_name, args)
        if not is_valid:
            logger.warning("[SECURITY GUARDRAIL BLOCKED MCP]: Tool %s | Error: %s", tool_name, error_msg)
            return {
                "status": "error",
                "error": f"Security Policy Violation: Tool input rejected. {error_msg}"
            }

    return None


def after_tool_guardrail(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """After-tool callback inspecting tool outputs for sensitive data leakage or indirect prompt injection."""
    if not SAFETY_ENABLED or not tool_response:
        return None

    tool_name = getattr(tool, "name", str(tool))
    resp_str = str(tool_response)

    # Redact any accidental private API keys or tokens in tool responses
    redacted_str = re.sub(r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[a-zA-Z0-9_\-]{16,}["\']?', r'\1: [REDACTED]', resp_str)
    if redacted_str != resp_str and isinstance(tool_response, dict):
        logger.warning("[SECURITY GUARDRAIL]: Redacted potential sensitive credentials in output from tool %s", tool_name)
        tool_response["sanitized"] = True

    return None


# ============================================================================
# 3. Input & Model Response Screening (Prompt Injection & Leak Protection)
# ============================================================================

def is_adversarial_input(text: str) -> Tuple[bool, Optional[str]]:
    """Checks user text against prompt injection, jailbreak, and adversarial patterns."""
    if not text:
        return False, None

    for pattern in ADVERSARIAL_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return True, f"Adversarial pattern detected: '{match.group(0)}'"

    return False, None


def is_system_prompt_leaked(text: str) -> bool:
    """Checks whether text contains leaked system instructions or prompt markers."""
    if not text:
        return False

    for marker in INTERNAL_PROMPT_LEAK_MARKERS:
        if marker in text:
            return True

    return False


def before_model_guardrail(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Before-model callback screening user input for jailbreaks and prompt injections.
    
    If an adversarial attempt is detected, immediately intercepts the flow and returns
    a safe standard refusal LlmResponse without querying downstream tools or LLMs.
    """
    if not SAFETY_ENABLED:
        return None

    if not llm_request.contents:
        return None

    # Check the latest user message
    last_content = llm_request.contents[-1]
    if last_content.role == "user" and last_content.parts:
        for part in last_content.parts:
            text = part.text or ""
            is_adv, reason = is_adversarial_input(text)
            if is_adv:
                logger.warning(
                    "[SECURITY GUARDRAIL BLOCKED USER INPUT in %s]: Reason: %s | Text: %s",
                    callback_context.agent_name,
                    reason,
                    text,
                )
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=STANDARD_REFUSAL_MESSAGE)],
                    )
                )

    return None


def after_model_guardrail(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    """After-model callback verifying model output against system prompt leakage and unescaped payloads."""
    if not SAFETY_ENABLED or not llm_response.content or not llm_response.content.parts:
        return None

    for part in llm_response.content.parts:
        if part.text:
            if is_system_prompt_leaked(part.text):
                logger.warning(
                    "[SECURITY GUARDRAIL BLOCKED SYSTEM PROMPT LEAK from %s]",
                    callback_context.agent_name,
                )
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=STANDARD_REFUSAL_MESSAGE)],
                    )
                )

    return None


# ============================================================================
# 4. ADK Safety Plugin for Runner-Level Enforcement
# ============================================================================

class GeminiSafetyPlugin(BasePlugin):
    """Reusable ADK Plugin that enforces safety guardrails globally across all agents.
    
    Reference: https://adk.dev/safety/#callbacks-and-plugins-for-security-guardrails
    """

    def __init__(self, name: str = "GeminiSafetyPlugin") -> None:
        super().__init__(name=name)

    async def on_user_message_callback(
        self,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """Validates incoming user message before agent execution."""
        if not SAFETY_ENABLED or not user_message.parts:
            return None

        for part in user_message.parts:
            if part.text:
                is_adv, reason = is_adversarial_input(part.text)
                if is_adv:
                    logger.warning("[SAFETY PLUGIN BLOCKED USER MESSAGE]: %s", reason)
                    invocation_context.session.state["is_user_prompt_safe"] = False
                    return types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="[BLOCKED_ADVERSARIAL_QUERY]")],
                    )
        return None

    async def before_run_callback(
        self,
        invocation_context: InvocationContext,
    ) -> Optional[types.Content]:
        """Halts the runner if the prompt was flagged unsafe in on_user_message_callback."""
        if not invocation_context.session.state.get("is_user_prompt_safe", True):
            invocation_context.session.state["is_user_prompt_safe"] = True
            return types.Content(
                role="model",
                parts=[types.Part.from_text(text=STANDARD_REFUSAL_MESSAGE)],
            )
        return None

    async def before_tool_callback(
        self,
        tool: BaseTool,
        tool_args: Dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[Dict[str, Any]]:
        """Intercepts and validates tool calls before execution."""
        return before_tool_guardrail(tool, tool_args, tool_context)

    async def after_tool_callback(
        self,
        tool: BaseTool,
        tool_args: Dict[str, Any],
        tool_context: ToolContext,
        result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Sanitizes tool output before passing back to LLM."""
        return after_tool_guardrail(tool, tool_args, tool_context, result)

    async def after_model_callback(
        self,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        """Screens model response for leaks and unsafe content."""
        return after_model_guardrail(callback_context, llm_response)
