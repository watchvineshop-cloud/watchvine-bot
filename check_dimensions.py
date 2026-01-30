
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("Google_api")
genai.configure(api_key=api_key)

try:
    # Try requesting 768 dimensions
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content="Hello world",
        task_type="retrieval_query",
        output_dimensionality=768
    )
    print(f"SUCCESS: Generated embedding with length {len(result['embedding'])}")
except Exception as e:
    print(f"FAILED: {e}")
