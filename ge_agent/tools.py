from google.adk.tools.bigquery import BigQueryToolset, BigQueryToolConfig
from .config import GOOGLE_CLOUD_PROJECT

bigquery_toolset = BigQueryToolset(
    tool_filter=["execute_sql"],
    bigquery_tool_config=BigQueryToolConfig(
        compute_project_id=GOOGLE_CLOUD_PROJECT
    )
)
