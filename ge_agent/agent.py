# An expert Technical Support Engineer and Documentation Assistant for Gemini Enterprise and Google Cloud Release Notes.

from google.adk.agents import Agent
from .callback_logging import log_query_to_model, log_model_response
from .prompt import SYSTEM_INSTRUCTION
from .mcp import documentation_mcp
from .tools import bigquery_toolset
from .config import MODEL

root_agent = Agent(
    model=MODEL,
    name="google_knowledge_agent",
    description="An expert Technical Support and GCP Documentation agent for Gemini Enterprise and Google Cloud Release Notes.",
    instruction=SYSTEM_INSTRUCTION,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    tools=[
        documentation_mcp,
        bigquery_toolset
    ],
)
