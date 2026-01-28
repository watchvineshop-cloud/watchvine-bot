#!/usr/bin/env python3
"""
Complete Startup Flow for WatchVine Bot
Handles: scraping, deduplication, enhancement, AI analysis, indexing
"""

import os
import sys
import logging
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
# Use Atlas for products
MONGODB_ATLAS_URI = os.getenv("MONGODB_ATLAS_URI")
MONGODB_URI = MONGODB_ATLAS_URI if MONGODB_ATLAS_URI else os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_ATLAS_DB", os.getenv("MONGODB_DB", "watchvine_refined"))
MIN_PRODUCT_COUNT = 10

def step_1_check_and_scrape():
    """Step 1: Check product count and scrape if needed"""
    logger.info("="*80)
    logger.info("STEP 1: CHECK PRODUCT COUNT & SCRAPE IF NEEDED")
    logger.info("="*80)
    
    try:
        from pymongo.server_api import ServerApi
        
        # Add SSL/TLS configuration for Atlas compatibility using Stable API
        if MONGODB_URI and 'mongodb+srv://' in MONGODB_URI:
            # Use MongoDB Stable API for better compatibility
            client = MongoClient(
                MONGODB_URI,
                server_api=ServerApi('1'),
                serverSelectionTimeoutMS=10000
            )
            client.admin.command('ping')
            logger.info("✅ MongoDB connected (Atlas with Stable API)")
        else:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            logger.info("✅ MongoDB connected")
        
        db = client[MONGODB_DB]
        products_col = db['products']
        
        # Count products
        product_count = products_col.count_documents({})
        logger.info(f"📊 Current products: {product_count}")
        
        if product_count < MIN_PRODUCT_COUNT:
            logger.warning(f"⚠️ Products ({product_count}) < minimum ({MIN_PRODUCT_COUNT})")
            logger.info("🚀 Starting scraper...")
            
            from fast_scraper import scrape_all_products
            scrape_all_products(watch_only=True, clear_db=False)
            
            logger.info("✅ Scraping completed")
        else:
            logger.info(f"✅ Sufficient products ({product_count} >= {MIN_PRODUCT_COUNT})")
            logger.info("⏭️ Skipping scraper")
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Step 1 failed: {e}", exc_info=True)
        return False

def step_2_remove_duplicates():
    """Step 2: Remove duplicate products"""
    logger.info("="*80)
    logger.info("STEP 2: REMOVE DUPLICATES")
    logger.info("="*80)
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        products = db['products']
        
        iteration = 1
        total_removed = 0
        
        while iteration <= 5:  # Max 5 iterations
            # Find duplicates
            pipeline = [
                {"$group": {
                    "_id": "$url",
                    "count": {"$sum": 1},
                    "ids": {"$push": "$_id"}
                }},
                {"$match": {"count": {"$gt": 1}}}
            ]
            
            duplicates = list(products.aggregate(pipeline))
            
            if not duplicates:
                logger.info(f"✅ No duplicates found!")
                break
            
            logger.info(f"🔄 Iteration {iteration}: Found {len(duplicates)} duplicate URLs")
            
            # Remove duplicates
            removed = 0
            for dup in duplicates:
                ids_to_delete = dup["ids"][1:]
                result = products.delete_many({"_id": {"$in": ids_to_delete}})
                removed += result.deleted_count
            
            total_removed += removed
            logger.info(f"  🗑️ Removed {removed} duplicates")
            iteration += 1
        
        # Create unique index
        try:
            products.create_index("url", unique=True)
            logger.info("✅ Created unique index on URL")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        logger.info(f"✅ Total duplicates removed: {total_removed}")
        
        # Final count
        final_count = products.count_documents({})
        logger.info(f"📊 Final product count: {final_count}")
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Step 2 failed: {e}", exc_info=True)
        return False

def step_3_enhance_new_products():
    """Step 3: Enhance only new products (without ai_analysis)"""
    logger.info("="*80)
    logger.info("STEP 3: ENHANCE NEW PRODUCTS")
    logger.info("="*80)
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        products = db['products']
        
        # Count products without AI analysis
        unenhanced = products.count_documents({"ai_analysis": {"$exists": False}})
        
        logger.info(f"📊 Products needing AI analysis: {unenhanced}")
        
        if unenhanced == 0:
            logger.info("✅ All products already enhanced")
            client.close()
            return True
        
        # Skip if too many products (run manually later)
        if unenhanced > 50:
            logger.warning(f"⚠️ {unenhanced} products need enhancement - SKIPPING for fast startup")
            logger.info("💡 Run manually: docker exec watchvine_bot python watch_enhancer.py")
            client.close()
            return True
        
        logger.info("🎨 Starting AI enhancement for new products...")
        
        from watch_enhancer import WatchEnhancer
        
        google_api_key = os.getenv("Google_api")
        enhancer = WatchEnhancer(MONGODB_URI, google_api_key=google_api_key, db_name=MONGODB_DB)
        
        try:
            # Only enhance products without ai_analysis
            enhancer.enhance_all_watches(ai_vision=True)
            logger.info("✅ Enhancement completed")
        finally:
            enhancer.close()
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Step 3 failed: {e}", exc_info=True)
        return False

def step_4_fix_empty_fields():
    """Step 4: Fill empty colors/styles/materials from AI data"""
    logger.info("="*80)
    logger.info("STEP 4: FIX EMPTY FIELDS FROM AI DATA")
    logger.info("="*80)
    
    try:
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        products = db['products']
        
        # Find products with ai_analysis but empty arrays
        query = {
            "ai_analysis": {"$exists": True},
            "$or": [
                {"colors": {"$size": 0}},
                {"styles": {"$size": 0}},
                {"materials": {"$size": 0}}
            ]
        }
        
        products_to_fix = list(products.find(query))
        total = len(products_to_fix)
        
        logger.info(f"📊 Found {total} products with empty fields")
        
        if total == 0:
            logger.info("✅ No products need fixing")
            client.close()
            return True
        
        fixed = 0
        for product in products_to_fix:
            try:
                ai_details = product.get('ai_analysis', {}).get('additional_details', {})
                
                colors = product.get('colors', [])
                materials = product.get('materials', [])
                styles = product.get('styles', [])
                
                # Extract from AI data
                dial_color = ai_details.get('dial_color', '').strip()
                strap_color = ai_details.get('strap_color', '').strip()
                strap_material = ai_details.get('strap_material', '').strip()
                case_material = ai_details.get('case_material', '').strip()
                watch_type = ai_details.get('watch_type', '').strip()
                
                # Add colors
                for color in [dial_color, strap_color]:
                    if color and color.lower() not in ['unknown', 'n/a', 'none']:
                        if color.title() not in colors:
                            colors.append(color.title())
                
                # Add materials
                for material in [strap_material, case_material]:
                    if material and material.lower() not in ['unknown', 'n/a', 'none']:
                        if material.title() not in materials:
                            materials.append(material.title())
                
                # Add styles
                if watch_type and watch_type.lower() not in ['unknown', 'n/a', 'none']:
                    if watch_type.title() not in styles:
                        styles.append(watch_type.title())
                
                # Update
                products.update_one(
                    {"_id": product["_id"]},
                    {"$set": {
                        "colors": colors,
                        "materials": materials,
                        "styles": styles
                    }}
                )
                
                fixed += 1
                
            except Exception as e:
                continue
        
        logger.info(f"✅ Fixed {fixed} products")
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Step 4 failed: {e}", exc_info=True)
        return False

def step_5_generate_embeddings():
    """Step 5: Generate text embeddings for products without embeddings"""
    logger.info("="*80)
    logger.info("STEP 5: GENERATE TEXT EMBEDDINGS")
    logger.info("="*80)
    
    try:
        import google.generativeai as genai
        import time
        
        google_api_key = os.getenv("Google_api")
        if not google_api_key:
            logger.warning("⚠️  Google API key not found, skipping embedding generation")
            return True
        
        genai.configure(api_key=google_api_key)
        
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        products = db.products
        
        # Check for products without embeddings
        without_embeddings = products.count_documents({"text_embedding": {"$exists": False}})
        
        if without_embeddings == 0:
            logger.info("✅ All products have embeddings")
            client.close()
            return True
        
        logger.info(f"📝 Generating embeddings for {min(without_embeddings, 50)} products (limit on startup)...")
        
        # Process products in batches - limit to 50 on startup to avoid delays
        products_to_process = list(products.find(
            {"text_embedding": {"$exists": False}},
            {
                "name": 1, "brand": 1, "category": 1, "searchable_text": 1,
                "colors": 1, "styles": 1, "materials": 1
            }
        ).limit(50))
        
        success_count = 0
        
        for product in products_to_process:
            try:
                # Create embedding text
                parts = [
                    product.get('name', ''),
                    product.get('brand', ''),
                    product.get('category', ''),
                    product.get('searchable_text', '')
                ]
                
                if product.get('colors'):
                    parts.append(' '.join(product['colors']))
                if product.get('styles'):
                    parts.append(' '.join(product['styles']))
                if product.get('materials'):
                    parts.append(' '.join(product['materials']))
                
                embedding_text = ' '.join(filter(None, parts)).strip()
                
                if not embedding_text:
                    continue
                
                # Generate embedding using embedding-001
                result = genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=embedding_text,
                    task_type="retrieval_document",
                    output_dimensionality=768
                )
                
                embedding = result['embedding']
                
                # Update product
                products.update_one(
                    {"_id": product["_id"]},
                    {"$set": {"text_embedding": embedding}}
                )
                
                success_count += 1
                
                # Rate limiting
                if success_count % 10 == 0:
                    time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Embedding error: {e}")
        
        logger.info(f"✅ Generated {success_count} embeddings")
        
        if without_embeddings > 50:
            logger.info(f"⚠️  {without_embeddings - 50} products still need embeddings")
            logger.info("   Run: docker exec watchvine_bot python tmp_rovodev_generate_embeddings.py")
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Embedding generation error: {e}")
        import traceback
        traceback.print_exc()
        return True  # Don't fail startup for embeddings

def step_6_create_image_index():
    """Step 6: Create FAISS index for image search"""
    logger.info("="*80)
    logger.info("STEP 6: CREATE IMAGE SEARCH INDEX")
    logger.info("="*80)
    
    try:
        # Check if index files already exist
        index_file = "/app/vector_index.bin"
        metadata_file = "/app/metadata.pkl"
        hash_file = "/app/hash_index.pkl"
        
        all_exist = os.path.exists(index_file) and os.path.exists(metadata_file) and os.path.exists(hash_file)
        
        if all_exist:
            logger.info("✅ Image search index already exists")
            logger.info("   Files found:")
            logger.info(f"   • {index_file}")
            logger.info(f"   • {metadata_file}")
            logger.info(f"   • {hash_file}")
            logger.info("⏭️ Skipping indexing")
            return True
        
        # Skip indexing on startup (too slow)
        logger.warning("⚠️ Image index not found - SKIPPING for fast startup")
        logger.info("💡 Run manually to enable image search:")
        logger.info("   docker exec -d watchvine_bot python indexer.py")
        logger.info("   (Takes ~10-15 minutes, runs in background)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Step 5 failed: {e}", exc_info=True)
        return True  # Don't fail startup

def main():
    """Run complete startup flow"""
    logger.info("="*80)
    logger.info("🚀 WATCHVINE STARTUP FLOW")
    logger.info("="*80)
    
    start_time = datetime.now()
    
    steps = [
        ("Check & Scrape", step_1_check_and_scrape),
        ("Remove Duplicates", step_2_remove_duplicates),
        ("AI Enhancement", step_3_enhance_new_products),
        ("Fix Empty Fields", step_4_fix_empty_fields),
        ("Generate Embeddings", step_5_generate_embeddings),
        ("Image Index", step_6_create_image_index)
    ]
    
    for step_name, step_func in steps:
        logger.info(f"\n▶️ Starting: {step_name}")
        success = step_func()
        
        if not success:
            logger.error(f"❌ Failed at: {step_name}")
            logger.error("🛑 Stopping startup flow")
            sys.exit(1)
        
        logger.info(f"✅ Completed: {step_name}")
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    logger.info("="*80)
    logger.info("🎉 STARTUP FLOW COMPLETE!")
    logger.info(f"⏱️ Total time: {elapsed:.1f} seconds")
    logger.info("="*80)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
