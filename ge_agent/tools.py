from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig
from .config import GOOGLE_CLOUD_PROJECT

bigquery_toolset = BigQueryToolset(
    tool_filter=["execute_sql"],
    bigquery_tool_config=BigQueryToolConfig(
        compute_project_id=GOOGLE_CLOUD_PROJECT
    )
)
