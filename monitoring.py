"""
Real-time Monitoring for WatchVine Bot
Provides stats and metrics for the bot
"""

import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class BotMonitor:
    def __init__(self, mongodb_uri: str, db_name: str):
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[db_name]
        self.products = self.db['products']
        self.conversations = self.db['conversations']
        self.search_cache = self.db['search_cache']
        
    def get_product_stats(self):
        """Get product statistics"""
        total_products = self.products.count_documents({})
        enhanced_products = self.products.count_documents({"enhanced_at": {"$exists": True}})
        ai_analyzed = self.products.count_documents({"ai_analysis": {"$exists": True}})
        with_embeddings = self.products.count_documents({"text_embedding": {"$exists": True}})
        
        # Category breakdown
        mens_watches = self.products.count_documents({"category_key": "mens_watch"})
        womens_watches = self.products.count_documents({"category_key": "womens_watch"})
        
        # Brand breakdown (top 10)
        brand_pipeline = [
            {"$match": {"brand": {"$ne": None}}},
            {"$group": {"_id": "$brand", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        top_brands = list(self.products.aggregate(brand_pipeline))
        
        # Price range breakdown
        price_pipeline = [
            {"$match": {"price_range": {"$ne": None}}},
            {"$group": {"_id": "$price_range", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        price_ranges = list(self.products.aggregate(price_pipeline))
        
        return {
            "total_products": total_products,
            "enhanced_products": enhanced_products,
            "ai_analyzed": ai_analyzed,
            "with_embeddings": with_embeddings,
            "enhancement_percentage": round((enhanced_products / total_products * 100) if total_products > 0 else 0, 1),
            "ai_analysis_percentage": round((ai_analyzed / total_products * 100) if total_products > 0 else 0, 1),
            "mens_watches": mens_watches,
            "womens_watches": womens_watches,
            "top_brands": [{"brand": b["_id"], "count": b["count"]} for b in top_brands],
            "price_ranges": [{"range": p["_id"], "count": p["count"]} for p in price_ranges]
        }
    
    def get_conversation_stats(self, hours: int = 24):
        """Get conversation statistics"""
        time_threshold = datetime.now() - timedelta(hours=hours)
        
        total_conversations = self.conversations.count_documents({})
        recent_conversations = self.conversations.count_documents({
            "timestamp": {"$gte": time_threshold}
        })
        
        # Unique users
        unique_users = len(self.conversations.distinct("phone_number"))
        recent_users = len(self.conversations.distinct("phone_number", {
            "timestamp": {"$gte": time_threshold}
        }))
        
        # Messages per hour (last 24 hours)
        hourly_pipeline = [
            {"$match": {"timestamp": {"$gte": time_threshold}}},
            {"$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d %H:00",
                        "date": "$timestamp"
                    }
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        hourly_messages = list(self.conversations.aggregate(hourly_pipeline))
        
        return {
            "total_conversations": total_conversations,
            "recent_conversations_24h": recent_conversations,
            "unique_users": unique_users,
            "recent_users_24h": recent_users,
            "hourly_messages": [{"hour": h["_id"], "count": h["count"]} for h in hourly_messages]
        }
    
    def get_search_stats(self):
        """Get search statistics"""
        if not self.search_cache:
            return {
                "total_searches": 0,
                "recent_searches": []
            }
        
        total_searches = self.search_cache.count_documents({})
        
        # Recent searches
        recent = list(
            self.search_cache.find({})
            .sort("timestamp", -1)
            .limit(10)
        )
        
        return {
            "total_searches": total_searches,
            "recent_searches": [
                {
                    "query": s.get("query", ""),
                    "products_found": s.get("total_found", 0),
                    "timestamp": s.get("timestamp", "").isoformat() if isinstance(s.get("timestamp"), datetime) else str(s.get("timestamp", ""))
                }
                for s in recent
            ]
        }
    
    def get_system_health(self):
        """Get system health status"""
        try:
            # Test MongoDB connection
            self.client.admin.command('ping')
            mongo_status = "connected"
        except Exception as e:
            mongo_status = f"error: {str(e)}"
        
        # Check if products need enhancement
        total = self.products.count_documents({})
        enhanced = self.products.count_documents({"enhanced_at": {"$exists": True}})
        needs_enhancement = total - enhanced
        
        return {
            "mongodb_status": mongo_status,
            "total_products": total,
            "products_needing_enhancement": needs_enhancement,
            "system_status": "healthy" if mongo_status == "connected" and needs_enhancement == 0 else "needs_attention",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_all_stats(self):
        """Get all statistics"""
        return {
            "products": self.get_product_stats(),
            "conversations": self.get_conversation_stats(),
            "searches": self.get_search_stats(),
            "system": self.get_system_health()
        }
    
    def close(self):
        """Close MongoDB connection"""
        self.client.close()
