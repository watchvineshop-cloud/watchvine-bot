
import os
import math
from pymongo import MongoClient
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB", "watchvine_refined")
GOOGLE_API_KEY = os.getenv("Google_api")

def dot_product(v1, v2):
    return sum(a * b for a, b in zip(v1, v2))

def magnitude(v):
    return math.sqrt(sum(a * a for a in v))

def cosine_similarity(v1, v2):
    return dot_product(v1, v2) / (magnitude(v1) * magnitude(v2))

def debug_search():
    if not GOOGLE_API_KEY:
        print("Error: Google_api not set")
        return

    genai.configure(api_key=GOOGLE_API_KEY)
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        collection = db['products']
        
        print("\n--- 1. Generating Query Embedding (New Model) ---")
        query = "rolex watch"
        print(f"Query: '{query}'")
        q_result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=query,
            task_type="retrieval_query",
            output_dimensionality=768
        )
        q_vec = q_result['embedding']
        print(f"Query Vector Start: {q_vec[:3]}...")
        
        print("\n--- 2. Inspecting Database Item ---")
        # Find a random product to check if it was updated
        # We look for one with 'embedding_generated_at' if it exists, or just any
        doc = collection.find_one()
        if doc:
            print(f"Product: {doc.get('name', 'Unknown')}")
            p_vec = doc.get('text_embedding')
            if p_vec:
                print(f"Stored Vector Start: {p_vec[:3]}...")
                
                # Check consistency
                # Old model typically produces values like 0.04... 
                # New model values should be checked.
                
                score = cosine_similarity(q_vec, p_vec)
                print(f"Similarity to Query: {score:.4f}")
                
                if score < 0.3:
                    print("⚠️  LOW SIMILARITY - Embeddings might be mismatched (Old vs New model)")
                else:
                    print("✅  Similarity looks reasonable")
            else:
                print("❌ No 'text_embedding' found in document!")
        else:
            print("❌ No products found in DB")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    debug_search()
