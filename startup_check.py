#!/usr/bin/env python3
"""
Startup Check Script
Checks product count and triggers scraping/enhancement if needed
"""

import os
import sys
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "watchvine_refined")
MIN_PRODUCT_COUNT = 10

def check_and_scrape():
    """Check product count and scrape if needed"""
    try:
        # Connect to MongoDB with explicit timeout
        logger.info(f"📡 Connecting to MongoDB...")
        logger.info(f"📡 URI: {MONGODB_URI[:30]}...")
        logger.info(f"📡 Database: {MONGODB_DB}")
        
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        logger.info("✅ MongoDB connection successful")
        
        db = client[MONGODB_DB]
        products_col = db['products']
        
        # List collections to verify
        collections = db.list_collection_names()
        logger.info(f"📋 Available collections: {collections}")
        
        # Count products
        product_count = products_col.count_documents({})
        logger.info(f"📊 Current product count: {product_count}")
        
        if product_count < MIN_PRODUCT_COUNT:
            logger.warning(f"⚠️ Product count ({product_count}) is below minimum ({MIN_PRODUCT_COUNT})")
            logger.info("🚀 Starting full scraper...")
            
            # Import and run scraper
            from fast_scraper import scrape_all_products
            
            # Scrape only watch products
            logger.info("🔍 Scraping watch products only...")
            scrape_all_products(watch_only=True, clear_db=False)
            
            logger.info("✅ Scraping completed")
        else:
            logger.info(f"✅ Product count is sufficient ({product_count} >= {MIN_PRODUCT_COUNT})")
            
            # Check if we should force scrape based on product quality
            watch_products = products_col.count_documents({
                "$or": [
                    {"category": {"$regex": "watch", "$options": "i"}},
                    {"name": {"$regex": "watch", "$options": "i"}}
                ]
            })
            
            if watch_products < MIN_PRODUCT_COUNT:
                logger.warning(f"⚠️ Only {watch_products} watch products found (total: {product_count})")
                logger.info("🚀 Starting watch scraper...")
                
                from fast_scraper import scrape_all_products
                scrape_all_products(watch_only=True, clear_db=False)
                
                logger.info("✅ Scraping completed")
            else:
                logger.info("⏭️ Skipping scraper - product inventory is good")
                logger.info("💡 Tip: To force re-scrape, set MIN_PRODUCT_COUNT higher or run fast_scraper.py manually")
        
        # Check for unenhanced products
        unenhanced_count = products_col.count_documents({"enhanced_at": {"$exists": False}})
        
        if unenhanced_count > 0:
            logger.info(f"🎨 Found {unenhanced_count} unenhanced products")
            logger.info("🚀 Starting enhancement...")
            
            # Import and run enhancer
            from watch_enhancer import WatchEnhancer
            
            google_api_key = os.getenv("Google_api")
            enhancer = WatchEnhancer(MONGODB_URI, google_api_key=google_api_key)
            try:
                enhancer.enhance_all_watches(ai_vision=True)
                enhancer.get_enhancement_summary()
            finally:
                enhancer.close()
            
            logger.info("✅ Enhancement completed")
        else:
            logger.info("✅ All products are enhanced")
        
        # Generate embeddings for products without them
        unembed_count = products_col.count_documents({"text_embedding": {"$exists": False}})
        
        if unembed_count > 0:
            logger.info(f"🔢 Found {unembed_count} products without embeddings")
            logger.warning("⚠️ Vector embeddings require MongoDB Atlas")
            logger.info("💡 Bot will use text-based search instead of vector search")
            logger.info("💡 To enable vector search, migrate to MongoDB Atlas")
        else:
            logger.info("✅ All products have embeddings")
        
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup check failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("🚀 WATCHVINE STARTUP CHECK")
    logger.info("="*80)
    
    success = check_and_scrape()
    
    if success:
        logger.info("\n✅ Startup check completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n❌ Startup check failed!")
        sys.exit(1)
