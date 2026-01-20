#!/usr/bin/env python3
"""
Watch Database Enhancement System
Automatically extracts brand, color, style, and other attributes from watch names and URLs
"""

import pymongo
from pymongo import MongoClient
import re
import requests
from typing import Dict, List, Optional
import time
import json
from datetime import datetime
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class WatchEnhancer:
    def __init__(self, mongodb_uri: str, google_api_key: str = None, db_name: str = "watchvine_refined"):
        self.mongodb_uri = mongodb_uri
        
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
        self.collection = self.db['products']
        
        # Initialize Gemini for AI vision analysis
        self.google_api_key = google_api_key or os.getenv("Google_api")
        if self.google_api_key:
            genai.configure(api_key=self.google_api_key)
            # Use gemini-2.0-flash specifically for vision/image analysis (2000 RPM)
            self.vision_model = genai.GenerativeModel('gemini-2.0-flash')
            print("✅ AI Vision analysis enabled (using gemini-2.0-flash for image analysis)")
        else:
            self.vision_model = None
            print("⚠️ AI Vision disabled (no API key)")
        
        # Enhanced patterns for better extraction
        self.brand_patterns = {
            'audemars_piguet': r'\b(audemars[_\s]*piguet|ap)\b',
            'patek_philippe': r'\b(patek[_\s]*philippe|pp)\b',
            'franck_muller': r'\b(franck[_\s]*muller|fm)\b',
            'rolex': r'\b(rolex|rlx)\b',
            'omega': r'\b(omega|omg)\b',
            'tag_heuer': r'\b(tag[_\s]*heuer|th)\b',
            'breitling': r'\b(breitling|brt)\b',
            'cartier': r'\b(cartier|cart)\b',
            'iwc': r'\b(iwc)\b',
            'jaeger_lecoultre': r'\b(jaeger[_\s]*lecoultre|jlc)\b',
            'vacheron_constantin': r'\b(vacheron[_\s]*constantin|vc)\b',
            'panerai': r'\b(panerai|pan)\b',
            'hublot': r'\b(hublot|hub)\b',
            'richard_mille': r'\b(richard[_\s]*mille|rm)\b',
            'casio': r'\b(casio|cas)\b',
            'seiko': r'\b(seiko|sei)\b',
            'citizen': r'\b(citizen|cit)\b',
            'tissot': r'\b(tissot|tis)\b',
            'hamilton': r'\b(hamilton|ham)\b',
            'fossil': r'\b(fossil|fos)\b',
            'daniel_wellington': r'\b(daniel[_\s]*wellington|dw)\b',
            'mvmt': r'\b(mvmt|movement)\b',
            'nixon': r'\b(nixon|nix)\b',
            'timex': r'\b(timex|tim)\b',
            'bulova': r'\b(bulova|bul)\b',
            'invicta': r'\b(invicta|inv)\b',
            'diesel': r'\b(diesel|die)\b',
            'armani': r'\b(armani|arm|emporio[_\s]*armani)\b',
            'gucci': r'\b(gucci|guc)\b',
            'versace': r'\b(versace|ver)\b',
            'boss': r'\b(boss|hugo[_\s]*boss)\b',
            'calvin_klein': r'\b(calvin[_\s]*klein|ck)\b',
            'tommy_hilfiger': r'\b(tommy[_\s]*hilfiger|th)\b',
            'michael_kors': r'\b(michael[_\s]*kors|mk)\b',
            'apple': r'\b(apple|iwatch)\b',
            'samsung': r'\b(samsung|galaxy[_\s]*watch)\b',
            'garmin': r'\b(garmin|gar)\b',
            'fitbit': r'\b(fitbit|fit)\b',
            'amazfit': r'\b(amazfit|amz)\b',
            'fire_boltt': r'\b(fire[_\s]*boltt|fireboltt)\b',
            'noise': r'\b(noise|noi)\b',
            'boat': r'\b(boat|bot)\b',
            'fastrack': r'\b(fastrack|fas)\b',
            'titan': r'\b(titan|tit)\b',
            'sonata': r'\b(sonata|son)\b',
            'maxima': r'\b(maxima|max)\b',
            'maybach': r'\b(maybach|may)\b'
        }
        
        self.color_patterns = {
            'black': r'\b(black|nero|schwarz|noir)\b',
            'white': r'\b(white|bianco|weiß|blanc|pearl)\b',
            'silver': r'\b(silver|argento|silber|argent|steel|stainless)\b',
            'gold': r'\b(gold|oro|gelb|or|yellow[_\s]*gold)\b',
            'rose_gold': r'\b(rose[_\s]*gold|pink[_\s]*gold|red[_\s]*gold)\b',
            'blue': r'\b(blue|blu|blau|bleu|navy|royal[_\s]*blue)\b',
            'red': r'\b(red|rosso|rot|rouge|burgundy|wine)\b',
            'green': r'\b(green|verde|grün|vert|olive|forest)\b',
            'brown': r'\b(brown|marrone|braun|brun|tan|cognac|leather)\b',
            'gray': r'\b(gray|grey|grigio|grau|gris|charcoal|slate)\b',
            'pink': r'\b(pink|rosa|rose|rose)\b',
            'purple': r'\b(purple|viola|lila|violet|lavender)\b',
            'orange': r'\b(orange|arancione|orange|coral)\b',
            'yellow': r'\b(yellow|giallo|gelb|jaune|golden)\b',
            'bronze': r'\b(bronze|bronzo|bronze)\b',
            'copper': r'\b(copper|rame|kupfer|cuivre)\b',
            'titanium': r'\b(titanium|titanio|titan)\b'
        }
        
        self.style_patterns = {
            'minimalistic': r'\b(minimal|minimalist|simple|clean|sleek|elegant|refined|classic|understated)\b',
            'sporty': r'\b(sport|sporty|athletic|diving|diver|racing|chronograph|tactical|rugged|outdoor)\b',
            'luxury': r'\b(luxury|premium|prestige|exclusive|haute|high[_\s]*end|elite|sophisticated)\b',
            'casual': r'\b(casual|everyday|daily|comfort|relaxed|informal)\b',
            'formal': r'\b(formal|dress|business|professional|office|executive|corporate)\b',
            'vintage': r'\b(vintage|retro|classic|heritage|traditional|antique)\b',
            'modern': r'\b(modern|contemporary|futuristic|innovative|cutting[_\s]*edge)\b',
            'smartwatch': r'\b(smart|digital|fitness|health|connected|wearable|tech)\b'
        }
        
        self.material_patterns = {
            'leather': r'\b(leather|cuoio|leder|cuir|strap|band)\b',
            'metal': r'\b(metal|steel|stainless|bracelet|chain|mesh)\b',
            'rubber': r'\b(rubber|silicone|sport[_\s]*band|flex)\b',
            'fabric': r'\b(fabric|canvas|nylon|textile|cloth)\b',
            'ceramic': r'\b(ceramic|ceramica|keramik)\b',
            'titanium': r'\b(titanium|titanio|titan)\b',
            'gold': r'\b(gold|golden|oro)\b',
            'silver': r'\b(silver|argento|silber)\b'
        }
    
    def extract_brand(self, text: str) -> Optional[str]:
        """Extract brand from product name or URL"""
        text_lower = text.lower()
        for brand, pattern in self.brand_patterns.items():
            if re.search(pattern, text_lower):
                return brand.replace('_', ' ').title()
        return None
    
    def extract_colors(self, text: str) -> List[str]:
        """Extract colors from product name or URL"""
        text_lower = text.lower()
        colors = []
        for color, pattern in self.color_patterns.items():
            if re.search(pattern, text_lower):
                colors.append(color.replace('_', ' ').title())
        return colors
    
    def extract_style(self, text: str) -> List[str]:
        """Extract style/type from product name or URL"""
        text_lower = text.lower()
        styles = []
        for style, pattern in self.style_patterns.items():
            if re.search(pattern, text_lower):
                styles.append(style.title())
        return styles
    
    def extract_materials(self, text: str) -> List[str]:
        """Extract materials from product name or URL"""
        text_lower = text.lower()
        materials = []
        for material, pattern in self.material_patterns.items():
            if re.search(pattern, text_lower):
                materials.append(material.title())
        return materials
    
    def extract_gender(self, category: str, name: str = "") -> str:
        """Extract gender from category or name"""
        text = f"{category} {name}".lower()
        if re.search(r'\b(men|male|homme|masculino)\b', text):
            return "Men"
        elif re.search(r'\b(women|female|femme|feminino|ladies|lady)\b', text):
            return "Women"
        elif re.search(r'\b(unisex|universal|both)\b', text):
            return "Unisex"
        else:
            return "Unisex"  # Default
    
    def extract_price_range(self, price: str) -> str:
        """Categorize price range"""
        try:
            price_num = float(price)
            if price_num < 1000:
                return "Budget (Under ₹1000)"
            elif price_num < 2500:
                return "Mid-Range (₹1000-2500)"
            elif price_num < 5000:
                return "Premium (₹2500-5000)"
            else:
                return "Luxury (₹5000+)"
        except:
            return "Unknown"
    
    def analyze_watch_image(self, image_url: str, product_name: str = "", max_retries: int = 3) -> Optional[Dict]:
        """Use Gemini Vision to analyze watch image and extract details with retry logic
        
        Args:
            image_url: URL of the watch image
            product_name: Product name to help determine if automatic
            max_retries: Number of retry attempts
        """
        if not self.vision_model:
            return None
        
        for attempt in range(max_retries):
            try:
                # Enhanced prompt for detailed watch analysis including new fields
                prompt = f"""Analyze this watch image and product name: "{product_name}"

Provide the following details in JSON format:
{{
    "dial_color": "color of the watch face/dial",
    "strap_material": "leather/metal/rubber/silicone/fabric",
    "strap_color": "color of the strap/bracelet",
    "watch_type": "analog/digital/smart/hybrid",
    "case_material": "stainless steel/gold/titanium/plastic/etc",
    "design_elements": ["list of notable design features like chronograph, date window, etc"],
    "is_automatic": "true/false - Is this an automatic/self-winding watch? Check product name for keywords: automatic, self-winding, auto, mechanical. If not mentioned, analyze if it looks like a mechanical/automatic watch",
    "watch_style_category": "Choose ONE from: professional/luxury/sports/casual/fashion/dress/diving/aviation/racing/vintage/modern/smartwatch"
}}

IMPORTANT for is_automatic:
- Look for keywords in product name: "automatic", "self-winding", "mechanical", "auto"
- If name mentions "quartz" or "battery", it's NOT automatic
- High-end luxury watches are often automatic
- Smart watches are NOT automatic

Provide only the JSON, no additional text."""
                
                # Download image
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()
                
                # Validate image content
                if len(img_response.content) < 1000:  # Too small to be valid
                    print(f"  ⚠️ Image too small, skipping")
                    return None
                
                # Determine mime type from content
                content_type = img_response.headers.get('content-type', 'image/jpeg')
                if 'image' not in content_type:
                    content_type = 'image/jpeg'  # Default to jpeg
                
                # Generate response with image
                response = self.vision_model.generate_content([
                    prompt,
                    {"mime_type": content_type, "data": img_response.content}
                ])
                
                # Parse JSON response
                result_text = response.text.strip()
                # Remove markdown code blocks if present
                if result_text.startswith("```"):
                    result_text = result_text.split("```")[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]
                
                analysis = json.loads(result_text.strip())
                return analysis
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a rate limit error
                if "429" in error_msg or "quota" in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = 60  # Wait 60 seconds for rate limit
                        print(f"  ⏳ Rate limit hit, waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"  ⚠️ Rate limit exceeded after {max_retries} attempts")
                        return None
                
                # Check if it's an invalid image error
                elif "400" in error_msg or "not valid" in error_msg.lower():
                    # Don't retry for invalid images, just skip
                    return None
                
                else:
                    print(f"  ⚠️ AI vision analysis failed: {e}")
                    return None
        
        return None
    
    def extract_is_automatic_from_name(self, name: str) -> bool:
        """Extract if watch is automatic from product name"""
        name_lower = name.lower()
        
        # Automatic indicators
        automatic_keywords = ['automatic', 'self-winding', 'self winding', 'auto', 'mechanical', 'kinetic']
        quartz_keywords = ['quartz', 'battery', 'digital']
        
        # Check for automatic keywords
        for keyword in automatic_keywords:
            if keyword in name_lower:
                return True
        
        # Check for quartz/battery (not automatic)
        for keyword in quartz_keywords:
            if keyword in name_lower:
                return False
        
        # Default to False if not specified
        return False
    
    def extract_watch_style_category(self, name: str, styles: List[str]) -> str:
        """Determine watch style category from name and extracted styles"""
        name_lower = name.lower()
        
        # Priority-based categorization
        if any(word in name_lower for word in ['smart', 'fitness', 'digital']):
            return 'smartwatch'
        elif any(word in name_lower for word in ['dive', 'diver', 'diving', 'submariner']):
            return 'diving'
        elif any(word in name_lower for word in ['pilot', 'aviation', 'aviator', 'flight']):
            return 'aviation'
        elif any(word in name_lower for word in ['racing', 'race', 'speedmaster', 'daytona']):
            return 'racing'
        elif any(word in name_lower for word in ['sport', 'sporty', 'athletic']):
            return 'sports'
        elif any(word in name_lower for word in ['dress', 'formal', 'business', 'elegant']):
            return 'dress'
        elif any(word in name_lower for word in ['vintage', 'classic', 'heritage']):
            return 'vintage'
        elif any(word in name_lower for word in ['luxury', 'prestige', 'haute']):
            return 'luxury'
        elif any(word in name_lower for word in ['professional', 'executive']):
            return 'professional'
        elif any(word in name_lower for word in ['casual', 'everyday']):
            return 'casual'
        elif any(word in name_lower for word in ['fashion', 'trendy', 'style']):
            return 'fashion'
        elif any(word in name_lower for word in ['modern', 'contemporary']):
            return 'modern'
        else:
            # Default based on price range
            try:
                price = float(product.get('price', '0'))
                if price > 10000:
                    return 'luxury'
                elif price > 5000:
                    return 'professional'
                else:
                    return 'casual'
            except:
                return 'casual'
    
    def enhance_watch_product(self, product: Dict) -> Dict:
        """Enhance a single watch product with extracted fields"""
        name = product.get('name', '')
        url = product.get('url', '')
        category = product.get('category', '')
        price = product.get('price', '0')
        image_urls = product.get('image_urls', [])
        
        # Combine text for analysis
        analysis_text = f"{name} {url} {category}"
        
        # Extract fields from text
        enhanced_product = product.copy()
        enhanced_product['brand'] = self.extract_brand(analysis_text)
        enhanced_product['colors'] = self.extract_colors(analysis_text)
        enhanced_product['styles'] = self.extract_style(analysis_text)
        enhanced_product['materials'] = self.extract_materials(analysis_text)
        enhanced_product['gender'] = self.extract_gender(category, name)
        enhanced_product['price_range'] = self.extract_price_range(price)
        enhanced_product['enhanced_at'] = datetime.now().isoformat()
        
        # NEW FIELDS: Extract from product name
        enhanced_product['is_automatic'] = self.extract_is_automatic_from_name(name)
        enhanced_product['watch_type'] = self.extract_watch_style_category(name, enhanced_product['styles'])
        
        # AI Vision Analysis (if image available and not already analyzed)
        if image_urls and self.vision_model and 'ai_analysis' not in enhanced_product:
            ai_details = self.analyze_watch_image(image_urls[0], product_name=name)
            if ai_details:
                enhanced_product['ai_analysis'] = {
                    "analyzed_at": datetime.now().isoformat(),
                    "image_analyzed": image_urls[0],
                    "additional_details": ai_details,
                    "api_model": "gemini-2.0-flash"
                }
                
                # Extract colors from AI analysis
                dial_color = ai_details.get('dial_color', '').strip()
                strap_color = ai_details.get('strap_color', '').strip()
                
                if dial_color and dial_color.lower() not in ['unknown', 'n/a', 'none']:
                    if dial_color.title() not in enhanced_product['colors']:
                        enhanced_product['colors'].append(dial_color.title())
                
                if strap_color and strap_color.lower() not in ['unknown', 'n/a', 'none']:
                    if strap_color.title() not in enhanced_product['colors']:
                        enhanced_product['colors'].append(strap_color.title())
                
                # Extract materials from AI analysis
                strap_material = ai_details.get('strap_material', '').strip()
                case_material = ai_details.get('case_material', '').strip()
                
                if strap_material and strap_material.lower() not in ['unknown', 'n/a', 'none']:
                    if strap_material.title() not in enhanced_product['materials']:
                        enhanced_product['materials'].append(strap_material.title())
                
                if case_material and case_material.lower() not in ['unknown', 'n/a', 'none']:
                    if case_material.title() not in enhanced_product['materials']:
                        enhanced_product['materials'].append(case_material.title())
                
                # Add watch type to styles
                watch_type_ai = ai_details.get('watch_type', '').strip()
                if watch_type_ai and watch_type_ai.lower() not in ['unknown', 'n/a', 'none']:
                    if watch_type_ai.title() not in enhanced_product['styles']:
                        enhanced_product['styles'].append(watch_type_ai.title())
                
                # Update is_automatic from AI if available
                is_automatic_ai = ai_details.get('is_automatic', '').strip().lower()
                if is_automatic_ai in ['true', 'yes', '1']:
                    enhanced_product['is_automatic'] = True
                elif is_automatic_ai in ['false', 'no', '0']:
                    enhanced_product['is_automatic'] = False
                # If AI says automatic, override name-based detection
                
                # Update watch_type from AI style category if available
                watch_style_category = ai_details.get('watch_style_category', '').strip().lower()
                if watch_style_category and watch_style_category not in ['unknown', 'n/a', 'none']:
                    enhanced_product['watch_type'] = watch_style_category
                
                # Determine belt type from AI analysis
                strap_material_lower = strap_material.lower()
                if 'metal' in strap_material_lower or 'steel' in strap_material_lower or 'gold' in strap_material_lower:
                    enhanced_product['belt_type'] = 'metal_belt'
                elif 'leather' in strap_material_lower:
                    enhanced_product['belt_type'] = 'leather_belt'
                elif 'rubber' in strap_material_lower or 'silicone' in strap_material_lower:
                    enhanced_product['belt_type'] = 'rubber_belt'
                else:
                    enhanced_product['belt_type'] = 'other'
        
        # Create searchable text
        searchable = f"{name} {category} {enhanced_product['brand'] or ''} "
        enhanced_product['searchable_text'] = searchable.lower()
        
        return enhanced_product
    
    def filter_only_watches(self) -> int:
        """Remove all non-watch products from database"""
        # Define what constitutes a watch
        watch_query = {
            "$or": [
                {"category": {"$regex": "watch", "$options": "i"}},
                {"name": {"$regex": "watch", "$options": "i"}},
                {"category": {"$in": ["Men's Watch", "Women's Watch", "Watch", "Watches"]}}
            ]
        }
        
        # Get non-watch products
        non_watch_query = {
            "$and": [
                {"$nor": [watch_query]},
                {"category": {"$not": {"$regex": "watch", "$options": "i"}}},
                {"name": {"$not": {"$regex": "watch", "$options": "i"}}}
            ]
        }
        
        # Count non-watch products
        non_watch_count = self.collection.count_documents(non_watch_query)
        print(f"Found {non_watch_count} non-watch products to remove")
        
        # Remove non-watch products
        if non_watch_count > 0:
            result = self.collection.delete_many(non_watch_query)
            print(f"Removed {result.deleted_count} non-watch products")
            return result.deleted_count
        
        return 0
    
    def enhance_all_watches(self, batch_size: int = 100, ai_vision: bool = True, only_new: bool = True):
        """Enhance watch products in the database
        
        Args:
            batch_size: Number of products to process before showing progress
            ai_vision: Whether to use AI vision analysis
            only_new: If True, only process products without ai_analysis (default)
        """
        # First filter to only watches
        self.filter_only_watches()
        
        # Build watch query
        watch_query = {
            "$or": [
                {"category": {"$regex": "watch", "$options": "i"}},
                {"name": {"$regex": "watch", "$options": "i"}},
            ]
        }
        
        if only_new:
            # Only process NEW products without AI analysis
            watch_query["ai_analysis"] = {"$exists": False}
            logger_msg = "NEW watch products (without AI analysis)"
        else:
            logger_msg = "ALL watch products"
        
        total_watches = self.collection.count_documents(watch_query)
        
        if total_watches == 0:
            print(f"✅ No {logger_msg} need enhancement")
            return 0
        
        print(f"Enhancing {total_watches} {logger_msg}...")
        
        if ai_vision and self.vision_model:
            print("🎨 AI Vision analysis enabled - extracting dial color, strap material, etc.")
        else:
            print("ℹ️  AI Vision disabled - only text-based enhancement")
        
        processed = 0
        ai_analyzed = 0
        
        for watch in self.collection.find(watch_query):
            try:
                had_ai_before = 'ai_analysis' in watch
                enhanced = self.enhance_watch_product(watch)
                
                # Track if AI analysis was added
                if 'ai_analysis' in enhanced and not had_ai_before:
                    ai_analyzed += 1
                
                # Update in database
                self.collection.replace_one(
                    {"_id": watch["_id"]},
                    enhanced
                )
                
                processed += 1
                if processed % batch_size == 0:
                    print(f"Processed {processed}/{total_watches} watches... (AI analyzed: {ai_analyzed})")
                
                # Rate limiting: 2000 requests per minute for gemini-2.0-flash
                # Minimal delay to stay under 2000 RPM
                # 2000 requests/60 seconds = 1 request per 0.03 seconds
                if ai_vision and self.vision_model and 'ai_analysis' in enhanced and not had_ai_before:
                    time.sleep(0.03)  # 30ms delay = ~2000 requests/minute
                    
            except Exception as e:
                print(f"Error processing watch {watch.get('name', 'Unknown')}: {e}")
                continue
        
        print(f"Enhancement complete! Processed {processed} watches.")
        print(f"✅ AI Vision analyzed: {ai_analyzed} watches")
        return processed
    
    def get_enhancement_summary(self):
        """Get summary of enhanced database"""
        total_watches = self.collection.count_documents({})
        
        # Aggregate by brand
        brands = self.collection.aggregate([
            {"$group": {"_id": "$brand", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ])
        
        # Aggregate by gender
        genders = self.collection.aggregate([
            {"$group": {"_id": "$gender", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ])
        
        # Aggregate by price range
        price_ranges = self.collection.aggregate([
            {"$group": {"_id": "$price_range", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ])
        
        print(f"\n=== ENHANCEMENT SUMMARY ===")
        print(f"Total Watch Products: {total_watches}")
        
        print(f"\nTop Brands:")
        for brand in brands:
            print(f"  - {brand['_id'] or 'Unknown'}: {brand['count']}")
        
        print(f"\nGender Distribution:")
        for gender in genders:
            print(f"  - {gender['_id']}: {gender['count']}")
        
        print(f"\nPrice Range Distribution:")
        for price_range in price_ranges:
            print(f"  - {price_range['_id']}: {price_range['count']}")
    
    def close(self):
        """Close database connection"""
        self.client.close()

if __name__ == "__main__":
    # MongoDB connection
    MONGODB_URI = "mongodb://admin:strongpassword123@72.62.76.36:27017/?authSource=admin"
    
    enhancer = WatchEnhancer(MONGODB_URI)
    
    try:
        print("Starting watch database enhancement...")
        enhancer.enhance_all_watches()
        enhancer.get_enhancement_summary()
        
    finally:
        enhancer.close()