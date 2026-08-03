import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

DEVELOPER_KNOWLEDGE_API_KEY = os.getenv('DEVELOPER_KNOWLEDGE_API_KEY', 'no_api_found')
GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'no_project_id_found')
MODEL = os.getenv('MODEL', 'gemini-2.5-pro')
