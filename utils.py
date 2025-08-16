import os
from google import genai
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key = os.getenv("GEMINI_API_KEY"))

def get_client():
    """
    Returns the GenAI client instance.
    """
    return client