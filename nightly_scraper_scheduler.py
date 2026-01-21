#!/usr/bin/env python3
"""
Nightly Automated Scraper & Database Updater
Runs every night at 12 AM (midnight)

Flow:
1. Scrape all watches from website
2. Compare with MongoDB database
3. Add new products
4. Remove products not on website (sold out)
5. AI enhancement for products missing fields (is_automatic, watch_type, etc.)
6. Run indexer.py for image search
7. System ready for next day
"""

import os
import sys
import time
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz

# Import existing modules
from fast_scraper import scrape_all_products
from watch_enhancer import WatchEnhancer
import subprocess

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/nightly_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_ATLAS_URI") or os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_ATLAS_DB") or os.getenv("MONGODB_DB", "watchvine_refined")
GOOGLE_API_KEY = os.getenv("Google_api")


def run_nightly_update():
    """Main nightly update function"""
    logger.info("=" * 80)
    logger.info("🌙 NIGHTLY AUTOMATED UPDATE STARTED")
    logger.info(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    try:
        # STEP 1: Scrape all watches from website
        logger.info("\n" + "=" * 80)
        logger.info("📥 STEP 1: SCRAPING WATCHES FROM WEBSITE")
        logger.info("=" * 80)
        
        # This will scrape, compare, and update database automatically
        scrape_all_products(
            watch_only=True,  # Only watches
            clear_db=False,   # Don't clear DB
            specific_categories=None,
            limit_per_category=None  # No limit
        )
        
        logger.info("✅ Step 1 complete: Scraping and database sync done")
        
        # STEP 2: AI Enhancement for missing fields
        logger.info("\n" + "=" * 80)
        logger.info("🎨 STEP 2: AI ENHANCEMENT FOR NEW/INCOMPLETE PRODUCTS")
        logger.info("=" * 80)
        
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        products_col = db['products']
        
        # Find products missing any required fields
        missing_fields_query = {
            "$or": [
                {"ai_analysis": {"$exists": False}},
                {"colors": {"$exists": False}},
                {"styles": {"$exists": False}},
                {"materials": {"$exists": False}},
                {"is_automatic": {"$exists": False}},
                {"watch_type": {"$exists": False}}
            ]
        }
        
        products_needing_enhancement = products_col.count_documents(missing_fields_query)
        
        if products_needing_enhancement > 0:
            logger.info(f"🔍 Found {products_needing_enhancement} products needing enhancement")
            
            # Run enhanced AI enhancement
            enhancer = WatchEnhancer(MONGODB_URI, google_api_key=GOOGLE_API_KEY, db_name=MONGODB_DB)
            try:
                # Run enhancement on products missing fields
                enhancer.enhance_all_watches(
                    batch_size=50,
                    ai_vision=True,
                    only_new=True  # Only products without ai_analysis
                )
                enhancer.get_enhancement_summary()
            finally:
                enhancer.close()
            
            logger.info("✅ Step 2 complete: AI enhancement done")
        else:
            logger.info("✅ Step 2 skipped: All products already enhanced")
        
        client.close()
        
        # STEP 3: Run image indexer
        logger.info("\n" + "=" * 80)
        logger.info("🖼️ STEP 3: REBUILDING IMAGE SEARCH INDEX")
        logger.info("=" * 80)
        
        # Run indexer.py as subprocess
        indexer_result = subprocess.run(
            ["python", "indexer.py"],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if indexer_result.returncode == 0:
            logger.info("✅ Step 3 complete: Image indexing done")
            logger.info(indexer_result.stdout[-500:])  # Last 500 chars
        else:
            logger.error(f"❌ Step 3 failed: Indexer error")
            logger.error(indexer_result.stderr[-500:])
        
        # Summary
        elapsed = time.time() - start_time
        logger.info("\n" + "=" * 80)
        logger.info("✅ NIGHTLY UPDATE COMPLETED SUCCESSFULLY")
        logger.info(f"⏱️ Total time: {elapsed/60:.2f} minutes")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ NIGHTLY UPDATE FAILED: {e}", exc_info=True)
        return False


def start_scheduler():
    """Start the APScheduler"""
    logger.info("🚀 Starting Nightly Scraper Scheduler")
    logger.info("⏰ Scheduled to run every day at 12:00 AM IST (India Standard Time)")
    
    # Import timezone support
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from pytz import timezone
    
    # Set timezone to India Standard Time
    ist = timezone('Asia/Kolkata')
    
    scheduler = BlockingScheduler(timezone=ist)
    
    # Schedule job for 12 AM IST every day
    scheduler.add_job(
        run_nightly_update,
        trigger=CronTrigger(hour=0, minute=0, timezone=ist),  # 12:00 AM IST
        id='nightly_scraper',
        name='Nightly Watch Database Update',
        replace_existing=True
    )
    
    logger.info("✅ Scheduler started successfully")
    logger.info(f"⏰ Timezone: Asia/Kolkata (IST)")
    logger.info("📅 Next run: Tonight at 12:00 AM IST")
    
    # For testing: Uncomment to run immediately
    # logger.info("🧪 Running test update immediately...")
    # run_nightly_update()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("⏹️ Scheduler stopped")


if __name__ == "__main__":
    start_scheduler()
