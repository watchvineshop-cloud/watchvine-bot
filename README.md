# WatchVine WhatsApp Bot 🤖⌚

AI-powered WhatsApp chatbot for a watch e-commerce store in Ahmedabad, India. Built with Gemini AI, MongoDB Vector Search, and Evolution API.

## 🌟 Features

- **AI-Powered Conversations**: Natural language understanding using Gemini 2.0 Flash
- **Vector Search**: Semantic product search with embeddings
- **Smart Scraping**: Auto-scrapes watch products when inventory is low
- **Product Enhancement**: AI extracts color, material, style, belt type from product images
- **Auto Cleanup**: Removes sold-out products automatically
- **Order Management**: Saves orders to Google Sheets
- **Multi-language**: Supports English and Gujarati

## 📁 Project Structure

```
watchvine/
├── main.py                          # Main Flask app with webhook handler
├── startup_check.py                 # Startup: scrape if <10 products, enhance, embed
├── agent_orchestrator.py            # Conversation flow orchestrator
├── backend_tool_classifier.py       # AI intent classifier
├── fast_scraper.py                  # Watch-only scraper with smart updates
├── watch_enhancer.py                # AI field extraction (color, material, etc.)
├── gemini_vector_search.py          # Vector search with Gemini embeddings
├── whatsapp_helper.py               # WhatsApp message/media sender
├── google_sheets_handler.py         # Order storage
├── store_config.py                  # Store information
├── system_prompt_config.py          # AI prompts
├── tool_calling_config.py           # Tool configurations
├── Dockerfile                       # Production Docker image
├── docker-compose.yml               # Docker compose setup
├── requirements.txt                 # Python dependencies
└── .env.example                     # Environment variables template
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- MongoDB
- Google Gemini API key
- Evolution API (WhatsApp)

### Installation

1. **Clone repository**
```bash
git clone <your-repo-url>
cd watchvine
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. **Run startup check** (scrapes if needed, enhances, embeds)
```bash
python startup_check.py
```

5. **Start the bot**
```bash
python main.py
```

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## 📊 Database Schema

### Product Document
```json
{
  "_id": ObjectId("..."),
  "name": "Audemars_piguet royal Oak Quartz",
  "url": "https://watchvine01.cartpe.in/...",
  "price": "2699.00",
  "image_urls": ["https://cdn.cartpe.in/..."],
  "category": "Men's Watch",
  "category_key": "mens_watch",
  "scraped_at": 1767984011.744455,
  
  // Enhanced fields (added by watch_enhancer.py)
  "brand": "Audemars Piguet",
  "colors": ["Silver", "Gold"],
  "styles": ["Luxury", "Formal"],
  "materials": ["Metal"],
  "gender": "Men",
  "price_range": "Premium (₹2500-5000)",
  "enhanced_at": "2026-01-17T22:38:43.229064",
  "searchable_text": "audemars_piguet royal oak quartz...",
  
  // AI analysis (added by watch_enhancer.py with Gemini Vision)
  "ai_analysis": {
    "analyzed_at": "2026-01-17T23:07:57.605720",
    "image_analyzed": "https://cdn.cartpe.in/...",
    "additional_details": {
      "dial_color": "silver",
      "strap_material": "stainless steel",
      "strap_color": "silver",
      "watch_type": "analog",
      "case_material": "stainless steel",
      "design_elements": ["date window", "textured dial"]
    },
    "api_model": "gemini-2.0-flash"
  },
  "belt_type": "metal_belt",
  
  // Vector embedding (added by gemini_vector_search.py)
  "text_embedding": [0.123, -0.456, ...],  // 768-dim vector
  "embedding_model": "models/embedding-001"
}
```

## 🔄 Workflow

### User Message Flow

1. **User sends message** → Evolution API webhook → `main.py`
2. **Intent Classification** → `backend_tool_classifier.py` analyzes intent
3. **Action Routing**:
   - `text_product_search` → Vector search via `gemini_vector_search.py`
   - `show_more` → Pagination from cached results
   - `order_collection` → `agent_orchestrator.py` handles order flow
   - `ai_chat` → General conversation via `agent_orchestrator.py`
4. **Response** → WhatsApp message sent via `whatsapp_helper.py`

### Startup Flow

1. **Check product count** → If < 10, trigger scraper
2. **Run scraper** → `fast_scraper.py` scrapes watches only
3. **Compare & Update** → Add new products, remove sold-out
4. **Enhance products** → `watch_enhancer.py` extracts fields with AI
5. **Generate embeddings** → `gemini_vector_search.py` creates vectors
6. **Start bot** → `main.py` listens for webhooks

## 🔧 Key Components

### 1. Startup Check (`startup_check.py`)
- Checks if product count < 10
- Triggers scraper if needed
- Enhances unenhanced products
- Generates embeddings for new products

### 2. Fast Scraper (`fast_scraper.py`)
- **Watch-only**: Filters non-watch products
- **Smart updates**: Compares with DB, adds new, removes sold-out
- **Multi-threaded**: Fast parallel scraping
- **Auto-retry**: Handles rate limiting

### 3. Watch Enhancer (`watch_enhancer.py`)
- Extracts brand, colors, materials, styles from name/URL
- Uses regex patterns for initial extraction
- Can be extended with Gemini Vision API for image analysis
- Categorizes price ranges
- Determines gender

### 4. Vector Search (`gemini_vector_search.py`)
- Generates text embeddings with Gemini
- Creates MongoDB vector search index
- Supports hybrid search (vector + filters)
- 768-dimensional embeddings

### 5. Main App (`main.py`)
- Flask webhook handler
- Conversation state management
- Product search with vector embeddings
- Order collection flow
- Pagination support

## 🎯 Environment Variables

```bash
# MongoDB
MONGODB_URI=mongodb://user:pass@host:port/?authSource=admin
MONGODB_DB=watchvine_refined

# Google AI
Google_api=your_gemini_api_key
google_model=gemini-2.0-flash-exp

# Evolution API (WhatsApp)
EVOLUTION_API_URL=http://your-evolution-api:8080
EVOLUTION_API_KEY=your_api_key
INSTANCE_NAME=shop-bot

# Google Sheets (Optional)
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/...
GOOGLE_APPS_SCRIPT_SECRET=your_secret

# Scraper
MONGO_URI=mongodb://user:pass@host:port/?authSource=admin
```

## 📈 Monitoring

### Check Product Count
```python
from pymongo import MongoClient
client = MongoClient("your_mongodb_uri")
db = client["watchvine_refined"]
count = db.products.count_documents({})
print(f"Products: {count}")
```

### Check Enhanced Products
```python
enhanced = db.products.count_documents({"enhanced_at": {"$exists": True}})
print(f"Enhanced: {enhanced}/{count}")
```

### Check Embeddings
```python
embedded = db.products.count_documents({"text_embedding": {"$exists": True}})
print(f"Embedded: {embedded}/{count}")
```

## 🛠️ Development

### Run Tests
```bash
# Test scraper
python fast_scraper.py

# Test enhancer
python watch_enhancer.py

# Test vector search
python gemini_vector_search.py
```

### Manual Scraping
```python
from fast_scraper import scrape_all_products
scrape_all_products(watch_only=True, clear_db=False)
```

### Manual Enhancement
```python
from watch_enhancer import WatchEnhancer
enhancer = WatchEnhancer("mongodb://...")
enhancer.enhance_all_watches()
enhancer.close()
```

### Generate Embeddings
```python
from gemini_vector_search import GeminiVectorSearch
vs = GeminiVectorSearch("mongodb://...", "gemini_api_key")
vs.index_all_products()
vs.close()
```

## 🚨 Troubleshooting

### Issue: No products in database
```bash
python startup_check.py  # Will auto-scrape
```

### Issue: Search not working
```bash
# Check embeddings
python -c "from gemini_vector_search import GeminiVectorSearch; vs = GeminiVectorSearch('mongodb://...', 'api_key'); print(vs.get_indexing_stats())"
```

### Issue: Products not enhanced
```bash
python watch_enhancer.py
```

## 📝 Notes

- **Watch-only focus**: Non-watch products are automatically filtered
- **Auto cleanup**: Sold-out products are removed automatically
- **Smart updates**: Only new products are added, no duplicates
- **Cost optimization**: Vector embeddings cached, AI calls minimized
- **Scalable**: Multi-threaded scraping, batch processing

## 🤝 Contributing

This is a private project for WatchVine store in Ahmedabad. Contact the owner for access.

## 📄 License

Proprietary - All rights reserved

---

**WatchVine** - Ahmedabad's Premium Watch Store 🇮🇳
Contact: 9016220667
