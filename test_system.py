#!/usr/bin/env python3
"""
System Test Script
Quick test to verify all components are working
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_mongodb_connection():
    """Test MongoDB connection"""
    print("🔍 Testing MongoDB connection...")
    try:
        from pymongo import MongoClient
        
        mongodb_uri = os.getenv("MONGODB_URI")
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        
        db = client[os.getenv("MONGODB_DB", "watchvine_refined")]
        count = db.products.count_documents({})
        
        print(f"✅ MongoDB connected - {count} products found")
        client.close()
        return True
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False

def test_gemini_api():
    """Test Gemini API"""
    print("\n🔍 Testing Gemini API...")
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("Google_api")
        if not api_key:
            print("❌ Google API key not found")
            return False
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        response = model.generate_content("Say 'Hello' in one word")
        print(f"✅ Gemini API working - Response: {response.text[:50]}")
        return True
    except Exception as e:
        print(f"❌ Gemini API failed: {e}")
        return False

def test_vector_search():
    """Test vector search system"""
    print("\n🔍 Testing Vector Search...")
    try:
        from gemini_vector_search import GeminiVectorSearch
        
        mongodb_uri = os.getenv("MONGODB_URI")
        google_api = os.getenv("Google_api")
        
        vs = GeminiVectorSearch(mongodb_uri, google_api)
        stats = vs.get_indexing_stats()
        
        print(f"✅ Vector Search OK")
        print(f"   Total Products: {stats['total_products']}")
        print(f"   Indexed: {stats['indexed_products']}")
        print(f"   Percentage: {stats['indexing_percentage']:.1f}%")
        
        vs.close()
        return True
    except Exception as e:
        print(f"❌ Vector Search failed: {e}")
        return False

def test_imports():
    """Test if all modules can be imported"""
    print("\n🔍 Testing Module Imports...")
    
    modules = [
        "agent_orchestrator",
        "backend_tool_classifier",
        "fast_scraper",
        "watch_enhancer",
        "gemini_vector_search",
        "whatsapp_helper",
        "google_sheets_handler",
        "store_config",
        "system_prompt_config",
        "tool_calling_config"
    ]
    
    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module}: {e}")
            failed.append(module)
    
    return len(failed) == 0

def main():
    print("="*80)
    print("🚀 WATCHVINE SYSTEM TEST")
    print("="*80)
    
    results = {
        "Imports": test_imports(),
        "MongoDB": test_mongodb_connection(),
        "Gemini API": test_gemini_api(),
        "Vector Search": test_vector_search()
    }
    
    print("\n" + "="*80)
    print("📊 TEST RESULTS")
    print("="*80)
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test:20s}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! System is ready.")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Please check configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()
