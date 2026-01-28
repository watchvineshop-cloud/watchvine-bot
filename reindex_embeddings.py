
import os
import time
import logging
from pymongo import MongoClient
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB", "watchvine_refined")
GOOGLE_API_KEY = os.getenv("Google_api")

def reindex_all_products():
    if not GOOGLE_API_KEY:
        logger.error("Google API Key not found!")
        return

    genai.configure(api_key=GOOGLE_API_KEY)
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        collection = db['products']
        
        products = list(collection.find())
        total = len(products)
        logger.info(f"Found {total} products to re-index...")
        
        success_count = 0
        
        for i, product in enumerate(products):
            try:
                # Create searchable text
                text_parts = [
                    product.get('name', ''),
                    product.get('brand', ''),
                    product.get('category', ''),
                    product.get('description', ''),
                    ' '.join(product.get('colors', [])),
                    ' '.join(product.get('styles', [])),
                    ' '.join(product.get('materials', [])),
                    product.get('searchable_text', '')
                ]
                
                searchable_text = ' '.join(filter(None, text_parts)).strip()[:9000] # Limit length
                
                # Generate NEW embedding with 768 dimensions
                result = genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=searchable_text,
                    task_type="retrieval_document",
                    output_dimensionality=768
                )
                
                embedding = result['embedding']
                
                # Update product
                collection.update_one(
                    {"_id": product["_id"]},
                    {"$set": {"text_embedding": embedding}}
                )
                
                success_count += 1
                if i % 10 == 0:
                    logger.info(f"Processed {i+1}/{total} products...")
                    time.sleep(1) # Rate limiting
                    
            except Exception as e:
                logger.error(f"Failed to index product {product.get('name')}: {e}")
                time.sleep(2)
        
        logger.info(f"Successfully re-indexed {success_count}/{total} products.")
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    reindex_all_products()
