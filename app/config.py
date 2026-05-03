import os
from dotenv import load_dotenv

load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-4.6-sonnet")

VLM_BASE_URL = os.getenv("VLM_BASE_URL", LLM_BASE_URL)
VLM_API_KEY = os.getenv("VLM_API_KEY", LLM_API_KEY)
VLM_MODEL = os.getenv("VLM_MODEL", "gemini-3.1-pro")
