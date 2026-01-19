"""
WatchVine WhatsApp Bot - Clean Architecture with Vector Search
Main entry point for the watch e-commerce chatbot
"""

import os
import logging
import time
from flask import Flask, request, jsonify
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai

# Import custom modules
from agent_orchestrator import AgentOrchestrator, ConversationState
from backend_tool_classifier import BackendToolClassifier
from google_sheets_handler import GoogleSheetsHandler, MongoOrderStorage
from google_apps_script_handler import GoogleAppsScriptHandler
from gemini_vector_search import GeminiVectorSearch
from whatsapp_helper import send_whatsapp_message, send_whatsapp_media
from monitoring import BotMonitor

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

GOOGLE_API_KEY = os.getenv("Google_api")
GOOGLE_MODEL = os.getenv("google_model", "gemini-2.5-flash")
# Local MongoDB for conversations
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "watchvine_refined")

# Atlas MongoDB for products with vector search
MONGODB_ATLAS_URI = os.getenv("MONGODB_ATLAS_URI", MONGODB_URI)  # Fallback to local if not set
MONGODB_ATLAS_DB = os.getenv("MONGODB_ATLAS_DB", MONGODB_DB)

# WhatsApp/Evolution API
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "shop-bot")

# Store Configuration
STORE_WEBSITE_URL = os.getenv("STORE_WEBSITE_URL", "https://watchvine01.cartpe.in/")
STORE_CONTACT_NUMBER = os.getenv("STORE_CONTACT_NUMBER", "+91 90162 20667")

if not GOOGLE_API_KEY:
    logger.error("⚠️ Google_api not set! AI features will fail.")
    exit(1)

genai.configure(api_key=GOOGLE_API_KEY)
logger.info(f"✅ Using Google Model: {GOOGLE_MODEL}")

# ============================================================================
# MONGODB CONNECTION
# ============================================================================

class ConversationManager:
    """Manage user conversations and search context in MongoDB"""

    def __init__(self, mongodb_uri: str, db_name: str):
        # Configure MongoDB client with Stable API for Atlas
        from pymongo.server_api import ServerApi
        
        if 'mongodb+srv://' in mongodb_uri:
            self.client = MongoClient(
                mongodb_uri,
                server_api=ServerApi('1'),
                serverSelectionTimeoutMS=10000
            )
        else:
            self.client = MongoClient(mongodb_uri)
        self.db = self.client[db_name]
        self.conversations = self.db.conversations
        self.search_cache = self.db.search_cache
        self.processed_messages = self.db.processed_messages
        
        # Create indexes
        self.conversations.create_index("phone_number")
        self.search_cache.create_index("phone_number")
        self.search_cache.create_index("expires_at")
        self.processed_messages.create_index("message_id", unique=True)
        self.processed_messages.create_index("timestamp", expireAfterSeconds=86400)  # Auto-delete after 24h
        
        logger.info("✅ MongoDB connected")

    def get_conversation(self, phone_number: str, limit: int = 10):
        """Get conversation history"""
        try:
            messages = list(
                self.conversations.find({"phone_number": phone_number})
                .sort("timestamp", -1)
                .limit(limit)
            )
            messages.reverse()
            return [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in messages if msg.get("content")
            ]
        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return []

    def save_message(self, phone_number: str, role: str, content: str):
        """Save message to history"""
        try:
            self.conversations.insert_one({
                "phone_number": phone_number,
                "role": role,
                "content": content,
                "timestamp": datetime.now()
            })
        except Exception as e:
            logger.error(f"Error saving message: {e}")

    def get_search_context(self, phone_number: str):
        """Get cached search context"""
        try:
            return self.search_cache.find_one({"phone_number": phone_number})
        except Exception as e:
            logger.error(f"Error getting search context: {e}")
            return None

    def save_search_context(self, phone_number: str, query: str, products: list, sent_count: int = 0):
        """Save search context for pagination"""
        try:
            self.search_cache.update_one(
                {"phone_number": phone_number},
                {
                    "$set": {
                        "query": query,
                        "products": products,
                        "total_found": len(products),
                        "sent_count": sent_count,
                        "timestamp": datetime.now()
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving search context: {e}")

    def clear_search_context(self, phone_number: str):
        """Clear search context"""
        try:
            self.search_cache.delete_one({"phone_number": phone_number})
        except Exception as e:
            logger.error(f"Error clearing search context: {e}")
    
    def is_message_processed(self, message_id: str) -> bool:
        """Check if message was already processed"""
        try:
            return self.processed_messages.find_one({"message_id": message_id}) is not None
        except Exception as e:
            logger.error(f"Error checking processed message: {e}")
            return False
    
    def mark_message_processed(self, message_id: str, phone_number: str):
        """Mark message as processed"""
        try:
            self.processed_messages.insert_one({
                "message_id": message_id,
                "phone_number": phone_number,
                "timestamp": datetime.now()
            })
        except Exception as e:
            logger.error(f"Error marking message as processed: {e}")

# ============================================================================
# PRODUCT SEARCH WITH VECTOR EMBEDDINGS
# ============================================================================

class ProductSearchHandler:
    """Handle product search using vector embeddings"""
    
    def __init__(self, vector_search: GeminiVectorSearch):
        self.vector_search = vector_search
    
    def search_products(self, query: str, filters: dict = None, limit: int = 50):
        """Search products using vector embeddings and filters"""
        try:
            logger.info(f"🔍 Vector search: '{query}' with filters: {filters}")
            
            # Perform hybrid search (vector + filters)
            if filters:
                results = self.vector_search.hybrid_search(
                    query=query,
                    filters=filters,
                    limit=limit
                )
            else:
                results = self.vector_search.vector_search(
                    query=query,
                    limit=limit
                )
            
            logger.info(f"✅ Found {len(results)} products")
            return results
            
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return []
    
    def format_product_message(self, product: dict) -> str:
        """Format product info for WhatsApp message"""
        name = product.get('name', 'Unknown')
        price = product.get('price', 'N/A')
        url = product.get('url', '')
        brand = product.get('brand', '')
        
        message = f"📦 {name}\n"
        if brand:
            message += f"🏷️ Brand: {brand}\n"
        message += f"💰 ₹{price}\n"
        if url:
            message += f"🔗 {url}"
        
        return message

# ============================================================================
# WHATSAPP MESSAGE HANDLER
# ============================================================================

def send_product_results(phone_number: str, products: list, query: str, start_index: int = 0, batch_size: int = 10):
    """Send product results to WhatsApp"""
    try:
        total_found = len(products)
        end_index = min(start_index + batch_size, total_found)
        products_to_send = products[start_index:end_index]
        
        # Send intro message
        intro_msg = f"""🎉 Found {total_found} watches for '{query}'!

Showing {len(products_to_send)} products ({start_index+1}-{end_index})...
📸 Sending images..."""
        
        send_whatsapp_message(phone_number, intro_msg)
        
        # Send products with images
        for product in products_to_send:
            image_urls = product.get('image_urls', [])
            if image_urls:
                caption = product_search_handler.format_product_message(product)
                send_whatsapp_media(phone_number, image_urls[0], caption)
            time.sleep(0.5)  # Rate limiting
        
        # Send Gujarati order instructions after products
        gujarati_msg = """તમે આ વસ્તુ બે રીતે ઓર્ડર કરી શકો છો:

1️⃣ અમદાવાદ-બોપાલ સ્થિત અમારા store પરથી સીધા આવીને લઈ શકો છો.

2️⃣ ઘરે બેઠા Open Box Cash on Delivery દ્વારા પણ મંગાવી શકો છો.

તમને કયો વિકલ્પ વધુ યોગ્ય લાગે છે? કૃપા કરીને જણાવશો."""
        
        send_whatsapp_message(phone_number, gujarati_msg)
        time.sleep(0.5)
        
        # Send completion message
        if end_index < total_found:
            completion_msg = f"""✅ Showing {end_index} of {total_found} products

📝 Type 'more' to see more watches
🔍 Or search with different keywords"""
        else:
            completion_msg = f"""✅ All {total_found} products shown!

🛒 Ready to order? Share product name
📞 Call us: {STORE_CONTACT_NUMBER}"""
        
        send_whatsapp_message(phone_number, completion_msg)
        
        return True, total_found, len(products_to_send)
        
    except Exception as e:
        logger.error(f"❌ Error sending products: {e}")
        return False, 0, 0

# ============================================================================
# FLASK APP & WEBHOOK
# ============================================================================

app = Flask(__name__)

# Initialize components
logger.info("🚀 Initializing WatchVine Bot...")

# Use local MongoDB for conversations
conversation_manager = ConversationManager(MONGODB_URI, MONGODB_DB)

# Use Atlas MongoDB for products with vector search
vector_search = GeminiVectorSearch(MONGODB_ATLAS_URI, GOOGLE_API_KEY, collection_name="products", db_name=MONGODB_ATLAS_DB)
product_search_handler = ProductSearchHandler(vector_search)
backend_classifier = BackendToolClassifier()
orchestrator = AgentOrchestrator(conversation_manager)
bot_monitor = BotMonitor(MONGODB_URI, MONGODB_DB)

# Initialize order storage
GOOGLE_APPS_SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL")
GOOGLE_APPS_SCRIPT_SECRET = os.getenv("GOOGLE_APPS_SCRIPT_SECRET")

if GOOGLE_APPS_SCRIPT_URL and GOOGLE_APPS_SCRIPT_SECRET:
    logger.info("🔧 Using Google Apps Script for order storage")
    order_storage = GoogleAppsScriptHandler(
        web_app_url=GOOGLE_APPS_SCRIPT_URL,
        secret_key=GOOGLE_APPS_SCRIPT_SECRET
    )
else:
    logger.info("🔧 Using MongoDB for order storage")
    order_storage = MongoOrderStorage(mongodb_uri=MONGODB_URI, db_name=MONGODB_DB)

logger.info("✅ Bot initialized successfully!")

# ============================================================================
# WEBHOOK HANDLERS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200

@app.route('/stats', methods=['GET'])
def stats():
    """Get real-time statistics"""
    try:
        all_stats = bot_monitor.get_all_stats()
        return jsonify(all_stats), 200
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Simple monitoring dashboard"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WatchVine Bot Monitor</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
            .container { max-width: 1400px; margin: 0 auto; }
            h1 { color: #38bdf8; margin-bottom: 10px; font-size: 2em; }
            .subtitle { color: #94a3b8; margin-bottom: 30px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .card { background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; }
            .card h2 { color: #38bdf8; margin-bottom: 16px; font-size: 1.2em; }
            .stat { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #334155; }
            .stat:last-child { border-bottom: none; }
            .stat-label { color: #94a3b8; font-size: 0.95em; }
            .stat-value { color: #38bdf8; font-weight: bold; font-size: 1.3em; }
            .badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: 600; }
            .badge-success { background: #065f46; color: #10b981; }
            .badge-warning { background: #92400e; color: #fbbf24; }
            .badge-info { background: #1e3a8a; color: #60a5fa; }
            .progress { background: #334155; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 8px; }
            .progress-bar { background: linear-gradient(90deg, #38bdf8, #06b6d4); height: 100%; transition: width 0.3s; }
            .refresh-btn { background: #38bdf8; color: #0f172a; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 1em; margin-bottom: 20px; }
            .refresh-btn:hover { background: #0ea5e9; }
            .timestamp { color: #64748b; font-size: 0.85em; margin-top: 20px; text-align: center; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            .loading { animation: pulse 1.5s ease-in-out infinite; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⌚ WatchVine Bot Monitor</h1>
            <p class="subtitle">Real-time monitoring dashboard</p>
            
            <button class="refresh-btn" onclick="loadStats()">🔄 Refresh Data</button>
            
            <div id="dashboard" class="loading">Loading...</div>
            <div class="timestamp" id="timestamp"></div>
        </div>
        
        <script>
            function formatNumber(num) {
                return num.toLocaleString();
            }
            
            function loadStats() {
                document.getElementById('dashboard').classList.add('loading');
                fetch('/stats')
                    .then(response => response.json())
                    .then(data => {
                        renderDashboard(data);
                        document.getElementById('dashboard').classList.remove('loading');
                        document.getElementById('timestamp').textContent = 'Last updated: ' + new Date().toLocaleString();
                    })
                    .catch(error => {
                        document.getElementById('dashboard').innerHTML = '<div class="card"><p style="color: #ef4444;">Error loading data: ' + error.message + '</p></div>';
                        document.getElementById('dashboard').classList.remove('loading');
                    });
            }
            
            function renderDashboard(data) {
                const products = data.products;
                const conversations = data.conversations;
                const searches = data.searches;
                const system = data.system;
                
                const html = `
                    <div class="grid">
                        <div class="card">
                            <h2>📦 Products</h2>
                            <div class="stat">
                                <span class="stat-label">Total Products</span>
                                <span class="stat-value">${formatNumber(products.total_products)}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Men's Watches</span>
                                <span class="stat-value">${formatNumber(products.mens_watches)}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Women's Watches</span>
                                <span class="stat-value">${formatNumber(products.womens_watches)}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Enhanced</span>
                                <span class="stat-value">${products.enhancement_percentage}%</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar" style="width: ${products.enhancement_percentage}%"></div>
                            </div>
                            <div class="stat">
                                <span class="stat-label">AI Analyzed</span>
                                <span class="stat-value">${products.ai_analysis_percentage}%</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar" style="width: ${products.ai_analysis_percentage}%"></div>
                            </div>
                        </div>
                        
                        <div class="card">
                            <h2>💬 Conversations</h2>
                            <div class="stat">
                                <span class="stat-label">Total Messages</span>
                                <span class="stat-value">${formatNumber(conversations.total_conversations)}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Last 24 Hours</span>
                                <span class="stat-value">${formatNumber(conversations.recent_conversations_24h)}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Unique Users</span>
                                <span class="stat-value">${formatNumber(conversations.unique_users)}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Active Users (24h)</span>
                                <span class="stat-value">${formatNumber(conversations.recent_users_24h)}</span>
                            </div>
                        </div>
                        
                        <div class="card">
                            <h2>🔍 Searches</h2>
                            <div class="stat">
                                <span class="stat-label">Total Searches</span>
                                <span class="stat-value">${formatNumber(searches.total_searches)}</span>
                            </div>
                            ${searches.recent_searches.slice(0, 5).map(s => `
                                <div class="stat">
                                    <span class="stat-label">${s.query || 'Unknown'}</span>
                                    <span class="badge badge-info">${s.products_found} found</span>
                                </div>
                            `).join('')}
                        </div>
                        
                        <div class="card">
                            <h2>🏷️ Top Brands</h2>
                            ${products.top_brands.slice(0, 8).map(b => `
                                <div class="stat">
                                    <span class="stat-label">${b.brand || 'Unknown'}</span>
                                    <span class="stat-value">${formatNumber(b.count)}</span>
                                </div>
                            `).join('')}
                        </div>
                        
                        <div class="card">
                            <h2>💰 Price Ranges</h2>
                            ${products.price_ranges.map(p => `
                                <div class="stat">
                                    <span class="stat-label">${p.range || 'Unknown'}</span>
                                    <span class="stat-value">${formatNumber(p.count)}</span>
                                </div>
                            `).join('')}
                        </div>
                        
                        <div class="card">
                            <h2>🔧 System Health</h2>
                            <div class="stat">
                                <span class="stat-label">MongoDB</span>
                                <span class="badge ${system.mongodb_status === 'connected' ? 'badge-success' : 'badge-warning'}">${system.mongodb_status}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Status</span>
                                <span class="badge ${system.system_status === 'healthy' ? 'badge-success' : 'badge-warning'}">${system.system_status}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Needs Enhancement</span>
                                <span class="stat-value">${formatNumber(system.products_needing_enhancement)}</span>
                            </div>
                        </div>
                    </div>
                `;
                
                document.getElementById('dashboard').innerHTML = html;
            }
            
            // Load stats on page load
            loadStats();
            
            // Auto-refresh every 30 seconds
            setInterval(loadStats, 30000);
        </script>
    </body>
    </html>
    """
    return html

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        data = request.json
        
        # Only process incoming messages
        if data.get('event') != 'messages.upsert':
            return jsonify({"status": "ignored"}), 200
        
        message_data = data.get('data', {})
        key_info = message_data.get('key', {})
        message_info = message_data.get('message', {})
        
        # Ignore messages from self
        if key_info.get('fromMe', False):
            return jsonify({"status": "ignored"}), 200
        
        # Ignore status updates (delivery receipts, read receipts, etc.)
        if not message_info or len(message_info) == 0:
            return jsonify({"status": "ignored"}), 200
        
        # Ignore if only contains messageStubType or other status fields
        if 'messageStubType' in message_data:
            return jsonify({"status": "ignored"}), 200
        
        # Extract message ID for deduplication
        message_id = key_info.get('id')
        if not message_id:
            return jsonify({"status": "error", "message": "no message ID"}), 400
        
        # Check if message was already processed
        if conversation_manager.is_message_processed(message_id):
            return jsonify({"status": "ignored", "reason": "already processed"}), 200
        
        # Extract phone number
        remote_jid = key_info.get('remoteJid', '')
        if not remote_jid:
            return jsonify({"status": "error", "message": "no phone number"}), 400
        
        phone_number = remote_jid.split('@')[0]
        
        # Extract message text
        conversation = (
            message_info.get('conversation') or
            message_info.get('extendedTextMessage', {}).get('text', '')
        )
        
        if not conversation:
            # Check for image message
            image_message = message_info.get('imageMessage')
            
            if image_message:
                logger.info(f"📸 Image received from {phone_number}")
                logger.info(f"📋 Image message structure: {list(image_message.keys())}")
                
                # Evolution API provides base64 encoded image data directly
                # Check for base64 data first (Evolution API v2)
                base64_data = message_data.get('base64')
                
                # Or try the imageMessage for base64
                if not base64_data and image_message:
                    base64_data = image_message.get('base64')
                
                logger.info(f"📋 Has base64 data: {bool(base64_data)}")
                
                if base64_data:
                    try:
                        import base64
                        import io
                        from PIL import Image
                        
                        logger.info(f"📥 Decoding base64 image data...")
                        
                        # Decode base64 to bytes
                        try:
                            image_bytes = base64.b64decode(base64_data)
                            logger.info(f"✅ Decoded {len(image_bytes)} bytes")
                        except Exception as e:
                            logger.error(f"Failed to decode base64: {e}")
                            send_whatsapp_message(phone_number, "માફ કરશો, તસવીર ડીકોડ કરવામાં સમસ્યા છે.\n\nSorry, couldn't decode the image.")
                            return jsonify({"status": "error"}), 200
                        
                        # Process and validate the image
                        try:
                            # Open and validate the image
                            image_bytes_io = io.BytesIO(image_bytes)
                            img = Image.open(image_bytes_io)
                            
                            # Convert to RGB if needed
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            
                            # Save to a new BytesIO as JPEG
                            output_bytes = io.BytesIO()
                            img.save(output_bytes, format='JPEG', quality=95)
                            output_bytes.seek(0)
                            
                            logger.info(f"✅ Image processed: {img.size}, mode: {img.mode}")
                            
                        except Exception as e:
                            logger.error(f"❌ Failed to process image: {e}")
                            send_whatsapp_message(phone_number, "માફ કરશો, તસવીર પ્રોસેસ કરવામાં સમસ્યા છે.\n\nSorry, couldn't process the image format.")
                            return jsonify({"status": "error"}), 200
                        
                        # Call image identifier service
                        image_identifier_url = "http://watchvine_image_identifier:8002/search"
                        
                        # Send processed image as multipart form file
                        files = {
                            'file': ('watch_image.jpg', output_bytes, 'image/jpeg')
                        }
                        
                        logger.info(f"📤 Sending image to identifier service...")
                        
                        response = requests.post(
                            image_identifier_url,
                            files=files,
                            timeout=30
                        )
                        
                        logger.info(f"📊 Image identifier response: {response.status_code}")
                        
                        if response.status_code != 200:
                            logger.error(f"❌ Image identifier error details: {response.text}")
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            logger.info(f"✅ Image identification result: {result.get('status')}")
                            
                            # Check if exact match or similar products found
                            if result.get('status') == 'exact_match':
                                # Found exact product
                                product_name = result.get('product_name')
                                product_url = result.get('product_url')
                                price = result.get('price', 'N/A')
                                
                                msg = f"""✅ આ ઘડિયાળ મળી ગઈ! / Watch Found!

📦 {product_name}
💰 Price: ₹{price}
🔗 {product_url}

શું તમે આ ઓર્ડર કરવા માંગો છો?
Would you like to order this?"""
                                
                                send_whatsapp_message(phone_number, msg)
                            
                            elif result.get('status') == 'similar_matches':
                                # Found similar products
                                matches = result.get('matches', [])
                                
                                if matches:
                                    logger.info(f"✅ Found {len(matches)} similar products")
                                    
                                    # Convert to product format expected by send_product_results
                                    products = []
                                    for match in matches:
                                        products.append({
                                            'name': match.get('product_name'),
                                            'url': match.get('product_url'),
                                            'price': match.get('price', 'N/A'),
                                            'image_urls': [match.get('image_url', '')],
                                            'similarity': match.get('similarity', 0)
                                        })
                                    
                                    # Send matching products
                                    success, total, sent = send_product_results(
                                        phone_number, 
                                        products, 
                                        "image search", 
                                        start_index=0, 
                                        batch_size=10
                                    )
                                    
                                    if success:
                                        conversation_manager.save_search_context(
                                            phone_number, 
                                            "image search", 
                                            products, 
                                            sent_count=sent
                                        )
                                else:
                                    send_whatsapp_message(
                                        phone_number, 
                                        "😔 આ તસવીર માટે કોઈ મેચિંગ ઘડિયાળ મળી નથી.\n\nSorry, no matching watches found for this image. Try searching by brand name!"
                                    )
                            else:
                                send_whatsapp_message(
                                    phone_number, 
                                    "😔 આ તસવીર માટે કોઈ મેચિંગ ઘડિયાળ મળી નથી.\n\nSorry, no matching watches found for this image. Try searching by brand name!"
                                )
                        else:
                            logger.error(f"Image identifier service error: {response.status_code}")
                            send_whatsapp_message(
                                phone_number,
                                "માફ કરશો, આ તસવીર પ્રોસેસ કરવામાં સમસ્યા છે.\n\nSorry, there was an issue processing the image."
                            )
                    
                    except Exception as e:
                        logger.error(f"Error calling image identifier: {e}")
                        send_whatsapp_message(
                            phone_number,
                            "માફ કરશો, આ તસવીર પ્રોસેસ કરવામાં સમસ્યા છે.\n\nSorry, there was an issue processing the image."
                        )
                
                return jsonify({"status": "success"}), 200
            
            # Non-text, non-image message
            logger.info(f"📸 Non-text message from {phone_number}")
            return jsonify({"status": "success"}), 200
        
        logger.info(f"📩 Message from {phone_number}: {conversation[:50]}...")
        
        # Mark message as processed
        conversation_manager.mark_message_processed(message_id, phone_number)
        
        # Save user message
        conversation_manager.save_message(phone_number, "user", conversation)
        
        # Get conversation history
        history = conversation_manager.get_conversation(phone_number, limit=10)
        
        # Check if user is in the middle of order collection
        user_state = orchestrator.get_user_state(phone_number)
        
        if user_state.name == 'COLLECTING_DETAILS' or user_state.name == 'AWAITING_FINAL_CONFIRMATION':
            # User is providing order details (name, address) or confirming
            logger.info(f"📝 User in order collection state: {user_state.value}")
            
            user_order = orchestrator.get_order_data(phone_number)
            
            # Check if user is confirming the order
            if user_state.name == 'AWAITING_FINAL_CONFIRMATION':
                if any(word in conversation.lower() for word in ['yes', 'confirm', 'ha', 'haan', 'ok', 'correct']):
                    # Save order to Google Sheets
                    try:
                        user_order.order_id = orchestrator._generate_order_id(phone_number)
                        user_order.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Save to Google Sheets
                        order_storage.save_order(user_order.to_dict())
                        
                        response = f"""✅ ઓર્ડર કન્ફર્મ થયો! / Order Confirmed!

🎉 Order ID: {user_order.order_id}

અમે તમને જલદી સંપર્ક કરીશું.
We will contact you soon!

આભાર! Thank you for shopping with WatchVine! 🛒"""
                        
                        send_whatsapp_message(phone_number, response)
                        
                        # Clear order data
                        orchestrator.clear_user_data(phone_number)
                        orchestrator.set_user_state(phone_number, orchestrator.ConversationState.ORDER_PLACED)
                        
                        return jsonify({"status": "success", "order_id": user_order.order_id}), 200
                    
                    except Exception as e:
                        logger.error(f"Error saving order: {e}")
                        error_msg = "માફ કરશો, ઓર્ડર સેવ કરવામાં સમસ્યા આવી.\n\nSorry, there was an issue saving your order. Please try again."
                        send_whatsapp_message(phone_number, error_msg)
                        return jsonify({"status": "error"}), 500
                else:
                    # User wants to make corrections
                    response = "કૃપા કરીને સુધારેલી વિગતો આપો.\n\nPlease provide the corrected details."
                    send_whatsapp_message(phone_number, response)
                    return jsonify({"status": "success"}), 200
            
            # Extract name or address from user's response
            if not user_order.customer_name:
                # User is providing name
                user_order.customer_name = conversation.strip()
                logger.info(f"✅ Name collected: {user_order.customer_name}")
                
                # Ask for address next
                response = "તમારું સરનામું શું છે?\n\nPlease provide your delivery address."
                send_whatsapp_message(phone_number, response)
                return jsonify({"status": "success"}), 200
            
            elif not user_order.address:
                # User is providing address
                user_order.address = conversation.strip()
                logger.info(f"✅ Address collected: {user_order.address}")
                
                # All details collected, show summary
                orchestrator.set_user_state(phone_number, orchestrator.ConversationState.AWAITING_FINAL_CONFIRMATION)
                
                summary = f"""✅ તમારા ઓર્ડરની વિગતો / Your Order Details:

📦 Product: {user_order.product_name or 'N/A'}
👤 Name: {user_order.customer_name}
📱 Phone: {user_order.phone_number}
📍 Address: {user_order.address}

શું તમે આ ઓર્ડર કન્ફર્મ કરવા માંગો છો?
Do you want to confirm this order?

Type "yes" to confirm or provide corrections."""
                
                send_whatsapp_message(phone_number, summary)
                return jsonify({"status": "success"}), 200
        
        # Classify intent using backend AI
        classification = backend_classifier.analyze_and_classify(history, conversation, phone_number)
        tool = classification.get('tool', 'ai_chat')
        
        logger.info(f"🔧 Classified as: {tool}")
        
        # Handle based on tool classification
        if tool == 'find_product' or tool == 'text_product_search':
            # Extract search parameters
            keyword = classification.get('keyword', '')
            category_key = classification.get('category_key')
            min_price = classification.get('min_price')
            max_price = classification.get('max_price')
            belt_type = classification.get('belt_type')
            colors = classification.get('colors')
            
            # Build query and filters
            query = keyword if keyword else conversation
            filters = {}
            
            if category_key:
                filters['category_key'] = category_key
            if min_price:
                filters['min_price'] = float(min_price)
            if max_price:
                filters['max_price'] = float(max_price)
            if belt_type:
                filters['belt_type'] = belt_type
            if colors:
                filters['colors'] = colors
            
            # Clear previous search context
            conversation_manager.clear_search_context(phone_number)
            
            # Perform search
            logger.info(f"🔍 Searching: query='{query}', filters={filters}")
            products = product_search_handler.search_products(query, filters, limit=50)
            
            if products:
                # Send products
                success, total, sent = send_product_results(phone_number, products, query, start_index=0, batch_size=10)
                
                if success:
                    # Save search context for pagination
                    conversation_manager.save_search_context(phone_number, query, products, sent_count=sent)
                    # Save bot response
                    conversation_manager.save_message(phone_number, "assistant", f"Found {total} products for '{query}'")
            else:
                error_msg = f"😔 Sorry, no products found for '{query}'. Try different keywords!"
                send_whatsapp_message(phone_number, error_msg)
                conversation_manager.save_message(phone_number, "assistant", error_msg)
        
        elif tool == 'show_more':
            # Handle pagination
            search_ctx = conversation_manager.get_search_context(phone_number)
            
            if search_ctx:
                products = search_ctx.get('products', [])
                query = search_ctx.get('query', '')
                sent_count = search_ctx.get('sent_count', 0)
                total_found = search_ctx.get('total_found', 0)
                
                if sent_count < total_found:
                    success, total, sent = send_product_results(
                        phone_number, products, query, 
                        start_index=sent_count, batch_size=10
                    )
                    
                    if success:
                        # Update sent count
                        conversation_manager.save_search_context(
                            phone_number, query, products, 
                            sent_count=sent_count + sent
                        )
                else:
                    send_whatsapp_message(phone_number, f"✅ You've seen all {total_found} products!")
            else:
                send_whatsapp_message(phone_number, "🔍 No active search. Please search for watches first!")
        
        elif tool == 'order_collection':
            # Handle order collection flow
            order_data = classification.get('order_data', {})
            response = orchestrator.handle_order_collection(phone_number, conversation, order_data)
            send_whatsapp_message(phone_number, response)
        
        elif tool == 'greeting':
            # Send welcome message with brand list
            greeting_message = """હેલો સર, Watchvine માં આપનું સ્વાગત છે! 🎉

સર, આપને શું જરૂરિયાત છે?

અમારી પાસે Fossil, Tissot, Armani, Tommy, Omega, Hublot, MK, Cartier, Tag Heuer, Rolex, Rado, AP અને Patek Philippe ઉપલબ્ધ છે.

કઈ કંપનીની જોઈએ છે તે કહેશો તો હું ફોટો મોકલું આપું."""
            
            send_whatsapp_message(phone_number, greeting_message)
            conversation_manager.save_message(phone_number, "assistant", greeting_message)
        
        else:
            # Default AI chat
            response = orchestrator.handle_general_chat(phone_number, conversation, history)
            send_whatsapp_message(phone_number, response)
            
            # Save AI response
            conversation_manager.save_message(phone_number, "assistant", response)
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🚀 Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
