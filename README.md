# Gemini Enterprise Knowledge Agent

A specialized Technical Support Engineer and Documentation Assistant built with the Google Agent Development Kit (ADK). This agent is designed to help users find accurate, up-to-date answers about Gemini Enterprise, products, and APIs by querying internal documentation via a Model Context Protocol (MCP) server.

## Features

- **Grounded Responses:** Employs strict grounding and anti-hallucination rules, answering queries solely based on internal documentation context.
- **Robust Search Workflow:** Implements multi-query fallback logic to iterate on search keywords if initial documentation queries return no results.
- **Auto-Citations:** Inline citations formatted as `[Document Title](URL)` mapping directly back to source documents.
- **Logging Integration:** Callback hooks to log all model requests, tool calls, and responses.

## Repository Structure

- [agent.py](ge_agent/agent.py) - Main agent configuration containing prompt instructions, model settings (Gemini 2.5 Pro), and the MCP toolset declaration.
- [callback_logging.py](ge_agent/callback_logging.py) - Hook functions that log requests to and responses from the LLM.
- `.env` - Environment variables configuration (API keys, Google Cloud project, region).

## Prerequisites & Installation

To manage dependencies, you can set up a virtual environment using either **uv** (recommended for speed) or the standard Python **venv** module.

### Option A: Using `uv` (Recommended)
```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install the required dependencies
uv pip install -r requirements.txt
```

### Option B: Using standard Python `venv`
```bash
# Create a virtual environment
python3 -m venv env

# Activate the virtual environment
source env/bin/activate

# Install the required dependencies
pip install -r requirements.txt
```

Set up your `.env` file inside the `ge_agent` directory with the following variables:

```ini
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_CLOUD_LOCATION=us-central1
DEVELOPER_KNOWLEDGE_API_KEY=<your-api-key>
```

## Running the Agent

You can interact with the agent using the ADK CLI tools included in the virtual environment.

### 1. Interactive CLI
Run an interactive session in your terminal with the agent:
```bash
adk run ge_agent
```

### 2. Web UI
Start a FastAPI server with a built-in Web interface:
```bash
adk web ge_agent
```

### 3. API Server
Start a FastAPI backend server exposing the agent as an endpoint:
```bash
adk api_server ge_agent
```
