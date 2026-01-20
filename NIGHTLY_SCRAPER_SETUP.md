# 🌙 Nightly Automated Scraper & Database Updater

## Overview

Automated system that runs every night at **12:00 AM** to:
1. ✅ Scrape all watches from website
2. ✅ Sync database (add new products, remove sold out)
3. ✅ AI enhancement for missing fields (is_automatic, watch_type, colors, materials, etc.)
4. ✅ Rebuild image search index
5. ✅ System ready for next day

---

## 🆕 New Fields Added

### 1. `is_automatic` (Boolean)
- Detects if watch is automatic/self-winding
- Extracted from product name keywords: "automatic", "self-winding", "mechanical"
- Can be overridden by AI vision analysis

### 2. `watch_type` (String)
- Categorizes watch style: `sports`, `dress`, `diving`, `professional`, `casual`, `luxury`, `smartwatch`, etc.
- Extracted from product name and AI analysis
- Searchable via backend_tool_classifier

### 3. Enhanced AI Analysis
- All existing fields: colors, materials, belt_type, ai_analysis
- New AI prompt includes automatic detection and watch style categorization

---

## 📋 Files Modified/Created

### New Files:
1. **`nightly_scraper_scheduler.py`** - Main scheduler (APScheduler-based)
   - Runs at 12 AM daily
   - Orchestrates scraping → enhancement → indexing

### Modified Files:
1. **`watch_enhancer.py`**
   - Added `extract_is_automatic_from_name()` method
   - Added `extract_watch_style_category()` method
   - Updated AI prompt to detect automatic and watch_type
   - Enhanced `enhance_watch_product()` to set new fields

2. **`backend_tool_classifier.py`**
   - Added detection rules for `is_automatic` field
   - Added detection rules for `watch_type` field
   - Updated examples with new field queries

3. **`fast_scraper.py`**
   - Already has `compare_and_update_database()` function (no changes needed)
   - Scrapes, compares, adds new, removes sold out

---

## 🚀 Installation & Setup

### Prerequisites
```bash
# Make sure you have these installed
pip install apscheduler  # For scheduling
```

### Step 1: Copy Files to Docker Container
```bash
# Copy new scheduler
docker cp nightly_scraper_scheduler.py watchvine_bot:/app/nightly_scraper_scheduler.py

# Copy updated files
docker cp watch_enhancer.py watchvine_bot:/app/watch_enhancer.py
docker cp backend_tool_classifier.py watchvine_bot:/app/backend_tool_classifier.py
docker cp fast_scraper.py watchvine_bot:/app/fast_scraper.py
```

### Step 2: Install Dependencies
```bash
# Install APScheduler in container
docker exec watchvine_bot pip install apscheduler
```

### Step 3: Create Log Directory
```bash
# Create logs directory if it doesn't exist
docker exec watchvine_bot mkdir -p /app/logs
```

### Step 4: Start Scheduler (Two Options)

#### Option A: Run in Background (Recommended)
```bash
# Start scheduler as background process
docker exec -d watchvine_bot python nightly_scraper_scheduler.py

# Check if running
docker exec watchvine_bot ps aux | grep nightly_scraper
```

#### Option B: Run in Separate Container (Better for Production)
Add to `docker-compose.yml`:

```yaml
  nightly_scraper:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: watchvine_nightly_scraper
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    command: python nightly_scraper_scheduler.py
    restart: unless-stopped
    depends_on:
      - bot
```

Then restart:
```bash
docker-compose up -d nightly_scraper
```

---

## 🧪 Testing

### Test Immediately (Don't Wait for Midnight)
Edit `nightly_scraper_scheduler.py` line 185:

```python
# Uncomment these lines for immediate test
logger.info("🧪 Running test update immediately...")
run_nightly_update()
```

Then run:
```bash
docker exec watchvine_bot python nightly_scraper_scheduler.py
```

### Test Individual Components

#### Test Scraper Only:
```bash
docker exec watchvine_bot python -c "from fast_scraper import scrape_all_products; scrape_all_products(watch_only=True, clear_db=False)"
```

#### Test AI Enhancement Only:
```bash
docker exec watchvine_bot python -c "from watch_enhancer import WatchEnhancer; import os; e = WatchEnhancer(os.getenv('MONGODB_URI'), os.getenv('Google_api')); e.enhance_all_watches(ai_vision=True, only_new=True); e.close()"
```

#### Test Indexer Only:
```bash
docker exec watchvine_bot python indexer.py
```

---

## 📊 Monitoring

### View Scheduler Logs:
```bash
# Live logs
docker exec watchvine_bot tail -f /app/logs/nightly_scraper.log

# Last 100 lines
docker exec watchvine_bot tail -100 /app/logs/nightly_scraper.log

# Search for errors
docker exec watchvine_bot grep ERROR /app/logs/nightly_scraper.log
```

### Check Scheduler Status:
```bash
# Check if scheduler is running
docker exec watchvine_bot ps aux | grep nightly_scraper

# Check scheduler process logs
docker logs watchvine_bot | grep "nightly"
```

### Verify Database Updates:
```bash
# Connect to MongoDB and check
docker exec watchvine_bot python -c "from pymongo import MongoClient; import os; c = MongoClient(os.getenv('MONGODB_URI')); db = c['watchvine_refined']; print(f'Total products: {db.products.count_documents({})}'); print(f'With is_automatic: {db.products.count_documents({\"is_automatic\": {\"$exists\": True}})}'); print(f'With watch_type: {db.products.count_documents({\"watch_type\": {\"$exists\": True}})}')"
```

---

## 🔍 Search with New Fields

### Example User Queries (Now Supported):

1. **"automatic watch dikhao"**
   - Searches for `is_automatic: true`

2. **"sports watch chahiye"**
   - Searches for `watch_type: "sports"`

3. **"rolex automatic watch"**
   - Searches for brand=rolex AND is_automatic=true

4. **"diving watch under 5000"**
   - Searches for watch_type=diving AND price < 5000

5. **"mechanical watch 2000 thi 3000"**
   - Searches for is_automatic=true AND price between 2000-3000

---

## ⚙️ Configuration

### Change Scheduler Time:
Edit `nightly_scraper_scheduler.py` line 173:

```python
# Current: Runs at 12:00 AM
scheduler.add_job(
    run_nightly_update,
    trigger=CronTrigger(hour=0, minute=0),  # Change hour/minute here
    ...
)

# Example: Run at 2:30 AM
trigger=CronTrigger(hour=2, minute=30)

# Example: Run every 6 hours
trigger=CronTrigger(hour='*/6')
```

### Adjust AI Rate Limiting:
Edit `watch_enhancer.py` line 456:

```python
# Current: 30ms delay = ~2000 requests/minute (gemini-2.0-flash limit)
time.sleep(0.03)

# If you hit rate limits, increase:
time.sleep(0.05)  # 1200 requests/minute
```

---

## 📈 MongoDB Atlas Vector Search

### ❓ Do You Need to Manually Update Vector Index?

**Answer: NO** - When you add new documents, Atlas automatically updates the index.

**BUT** - If you add NEW FIELDS to search (like `is_automatic`, `watch_type`), you need to update the index definition ONCE.

### Update Atlas Vector Search Index (One-Time):

1. Go to MongoDB Atlas Dashboard
2. Navigate to: Database → Search → Your Index
3. Edit Index Definition
4. Add new fields:

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "name": {
        "type": "string",
        "analyzer": "lucene.standard"
      },
      "brand": {
        "type": "string"
      },
      "colors": {
        "type": "string"
      },
      "materials": {
        "type": "string"
      },
      "belt_type": {
        "type": "string"
      },
      "is_automatic": {
        "type": "boolean"
      },
      "watch_type": {
        "type": "string"
      },
      "price": {
        "type": "number"
      },
      "category_key": {
        "type": "string"
      }
    }
  }
}
```

4. Click "Save" → Index will rebuild automatically (takes 5-10 minutes)

---

## 🛠️ Troubleshooting

### Scheduler Not Running:
```bash
# Check if process exists
docker exec watchvine_bot ps aux | grep nightly

# If not running, start it
docker exec -d watchvine_bot python nightly_scraper_scheduler.py

# Check for errors in logs
docker logs watchvine_bot --tail 50
```

### Scraper Fails:
```bash
# Check scraper logs
docker exec watchvine_bot tail -100 /app/logs/nightly_scraper.log

# Test scraper manually
docker exec watchvine_bot python fast_scraper.py
```

### AI Enhancement Hits Rate Limit:
```bash
# Check error in logs
docker exec watchvine_bot grep "429\|quota\|rate limit" /app/logs/nightly_scraper.log

# Solution: Increase delay in watch_enhancer.py (see Configuration section)
```

### Indexer Fails:
```bash
# Check if indexer.py exists
docker exec watchvine_bot ls -la indexer.py

# Run manually to see error
docker exec watchvine_bot python indexer.py
```

---

## 📞 Support & Questions

- Check logs first: `/app/logs/nightly_scraper.log`
- Test components individually (see Testing section)
- Verify environment variables are set correctly
- Ensure MongoDB connection is working

---

## ✅ Success Indicators

After first successful run, you should see:

1. **In Logs:**
   - "✅ NIGHTLY UPDATE COMPLETED SUCCESSFULLY"
   - Total time taken
   - Number of products scraped/added/removed

2. **In Database:**
   - New products added
   - Sold out products removed
   - `is_automatic` field populated
   - `watch_type` field populated

3. **In Image Indexer:**
   - New `vector_index.bin`, `metadata.pkl`, `hash_index.pkl` files

---

**🎉 Setup Complete! Your system will now update automatically every night at 12 AM.**
