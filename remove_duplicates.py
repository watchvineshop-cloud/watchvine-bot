#!/usr/bin/env python3
"""
Remove Duplicate Products from Database
Keeps only unique products based on URL
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "watchvine_refined")

def remove_duplicates():
    """Remove duplicate products based on URL"""
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    products = db['products']
    
    print("="*80)
    print("🔍 FINDING DUPLICATE PRODUCTS")
    print("="*80)
    
    # Count before
    total_before = products.count_documents({})
    print(f"\n📊 Total products before: {total_before}")
    
    # Find duplicates by URL
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
        print("\n✅ No duplicates found!")
        client.close()
        return
    
    print(f"\n⚠️  Found {len(duplicates)} URLs with duplicates")
    
    # Remove duplicates (keep first, delete rest)
    total_deleted = 0
    
    for dup in duplicates:
        url = dup["_id"]
        ids = dup["ids"]
        count = dup["count"]
        
        # Keep first ID, delete rest
        ids_to_delete = ids[1:]
        
        result = products.delete_many({"_id": {"$in": ids_to_delete}})
        deleted = result.deleted_count
        total_deleted += deleted
        
        print(f"  🗑️  {url[:60]}... - Removed {deleted} duplicates (had {count} copies)")
    
    # Count after
    total_after = products.count_documents({})
    
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Products before: {total_before}")
    print(f"Products after:  {total_after}")
    print(f"Duplicates removed: {total_deleted}")
    print(f"Unique products: {total_after}")
    
    # Create unique index on URL to prevent future duplicates
    try:
        products.create_index("url", unique=True)
        print("\n✅ Created unique index on 'url' field to prevent future duplicates")
    except Exception as e:
        print(f"\n⚠️  Could not create unique index: {e}")
    
    client.close()
    print("\n✅ Cleanup complete!")

if __name__ == "__main__":
    # Run multiple times until no duplicates found
    iteration = 1
    while True:
        print(f"\n{'='*80}")
        print(f"🔄 ITERATION {iteration}")
        print(f"{'='*80}")
        
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DB]
        products = db['products']
        
        # Check if duplicates exist
        pipeline = [
            {"$group": {
                "_id": "$url",
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        
        duplicates = list(products.aggregate(pipeline))
        client.close()
        
        if not duplicates:
            print(f"\n✅ No more duplicates found!")
            break
        
        print(f"Found {len(duplicates)} URLs with duplicates, cleaning...")
        remove_duplicates()
        
        iteration += 1
        
        if iteration > 10:
            print("\n⚠️ Reached max iterations (10), stopping")
            break
