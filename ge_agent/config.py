import os
from dotenv import load_dotenv
import certifi

# Ensure SSL certificates are properly located on macOS Python
os.environ.setdefault('SSL_CERT_FILE', certifi.where())
os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())

# Load env variables
load_dotenv()

DEVELOPER_KNOWLEDGE_API_KEY = os.getenv('DEVELOPER_KNOWLEDGE_API_KEY', 'no_api_found')
GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'no_project_id_found')
MODEL = os.getenv('MODEL', 'gemini-2.5-pro')

# Safety & Security Configuration (https://adk.dev/safety/)
SAFETY_ENABLED = os.getenv('SAFETY_ENABLED', 'true').lower() in ('true', '1', 'yes')
SAFETY_MODEL = os.getenv('SAFETY_MODEL', 'gemini-2.5-flash')
SAFETY_BLOCK_THRESHOLD = os.getenv('SAFETY_BLOCK_THRESHOLD', 'BLOCK_LOW_AND_ABOVE')
SAFETY_JUDGE_ENABLED = os.getenv('SAFETY_JUDGE_ENABLED', 'false').lower() in ('true', '1', 'yes')
ALLOWED_SQL_TABLES = [
    t.strip() for t in os.getenv(
        'ALLOWED_SQL_TABLES',
        'bigquery-public-data.google_cloud_release_notes.release_notes,google_cloud_release_notes.release_notes,release_notes'
    ).split(',') if t.strip()
]

