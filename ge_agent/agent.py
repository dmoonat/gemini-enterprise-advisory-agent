from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse

from .callback_logging import log_query_to_model, log_model_response
from .config import MODEL
from .mcp import documentation_mcp
from .prompt import SYSTEM_INSTRUCTION
from .safety import (
    after_model_guardrail,
    after_tool_guardrail,
    before_model_guardrail,
    before_tool_guardrail,
    build_generate_content_config,
)
from .tools import bigquery_toolset

# Import FinOps Plugin from installed package
from adk_finops import FinOpsCostPlugin

def handle_before_model(callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
    """Combines query logging with proactive prompt injection & adversarial screening."""
    log_query_to_model(callback_context, llm_request)
    return before_model_guardrail(callback_context, llm_request)


def handle_after_model(callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
    """Combines model response logging with system prompt leak protection and output screening."""
    guarded_response = after_model_guardrail(callback_context, llm_response)
    final_response = guarded_response or llm_response
    log_model_response(callback_context, final_response)
    return guarded_response


root_agent = Agent(
    model=MODEL,
    name="google_knowledge_agent",
    description="An expert Technical Support and GCP Documentation agent for Gemini Enterprise and Google Cloud Release Notes.",
    instruction=SYSTEM_INSTRUCTION,
    generate_content_config=build_generate_content_config(),
    before_model_callback=handle_before_model,
    after_model_callback=handle_after_model,
    before_tool_callback=before_tool_guardrail,
    after_tool_callback=after_tool_guardrail,
    tools=[
        documentation_mcp,
        bigquery_toolset
    ],
)

# 2. Instantiate the FinOps Plugin
finops_plugin = FinOpsCostPlugin(
        name="finops_cost_tracker",
        default_model=MODEL,
        budget_limit_usd=2.00,
        turn_budget_limit_usd=0.50,
        max_prompt_tokens=200_000,
        preflight_budget_guard=True,
        on_budget_exceeded="downgrade",
        fallback_model="gemini-3.5-flash",
        render_terminal_box=True,
        enable_optimization_advisor=True,
        jsonl_path="logs/finops_costs.jsonl",
        export_tags={"env": "dev", "team": "analytics"},
    )


# Create App with root agent and plugin
app = App(
    name="ge_agent",
    root_agent=root_agent,
    plugins=[finops_plugin],
)
