#!/usr/bin/env python3
"""
Fix Empty Colors, Styles, Materials from AI Analysis
Updates products that have ai_analysis but empty arrays
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "watchvine_refined")

def fix_empty_fields():
    """Fill empty colors/styles/materials from existing ai_analysis"""
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    products = db['products']
    
    print("="*80)
    print("🔧 FIXING EMPTY FIELDS FROM AI ANALYSIS")
    print("="*80)
    
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
    
    print(f"\n📊 Found {total} products with AI data but empty fields")
    
    if total == 0:
        print("✅ No products need fixing!")
        client.close()
        return
    
    fixed_count = 0
    
    for product in products_to_fix:
        try:
            ai_details = product.get('ai_analysis', {}).get('additional_details', {})
            
            # Extract colors
            colors = product.get('colors', [])
            dial_color = ai_details.get('dial_color', '').strip()
            strap_color = ai_details.get('strap_color', '').strip()
            
            if dial_color and dial_color.lower() not in ['unknown', 'n/a', 'none']:
                if dial_color.title() not in colors:
                    colors.append(dial_color.title())
            
            if strap_color and strap_color.lower() not in ['unknown', 'n/a', 'none']:
                if strap_color.title() not in colors:
                    colors.append(strap_color.title())
            
            # Extract materials
            materials = product.get('materials', [])
            strap_material = ai_details.get('strap_material', '').strip()
            case_material = ai_details.get('case_material', '').strip()
            
            if strap_material and strap_material.lower() not in ['unknown', 'n/a', 'none']:
                if strap_material.title() not in materials:
                    materials.append(strap_material.title())
            
            if case_material and case_material.lower() not in ['unknown', 'n/a', 'none']:
                if case_material.title() not in materials:
                    materials.append(case_material.title())
            
            # Extract styles
            styles = product.get('styles', [])
            watch_type = ai_details.get('watch_type', '').strip()
            
            if watch_type and watch_type.lower() not in ['unknown', 'n/a', 'none']:
                if watch_type.title() not in styles:
                    styles.append(watch_type.title())
            
            # Update product
            products.update_one(
                {"_id": product["_id"]},
                {"$set": {
                    "colors": colors,
                    "materials": materials,
                    "styles": styles
                }}
            )
            
            fixed_count += 1
            
            if fixed_count % 100 == 0:
                print(f"  ✅ Fixed {fixed_count}/{total} products...")
        
        except Exception as e:
            print(f"  ⚠️ Error fixing {product.get('name', 'Unknown')}: {e}")
            continue
    
    print(f"\n✅ Fixed {fixed_count} products!")
    
    # Show sample
    sample = products.find_one({"colors": {"$ne": []}})
    if sample:
        print(f"\n📦 Sample fixed product:")
        print(f"   Name: {sample.get('name', 'Unknown')}")
        print(f"   Colors: {sample.get('colors', [])}")
        print(f"   Materials: {sample.get('materials', [])}")
        print(f"   Styles: {sample.get('styles', [])}")
    
    client.close()
    print("\n✅ All done!")

if __name__ == "__main__":
    fix_empty_fields()
