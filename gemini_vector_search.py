#!/usr/bin/env python3
"""
Gemini Vector Search System for MongoDB
Uses Gemini text embeddings for semantic product search
"""

import google.generativeai as genai
import pymongo
from pymongo import MongoClient
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging
import time
import json
from datetime import datetime

class GeminiVectorSearch:
    def __init__(self, mongodb_uri: str, google_api_key: str, collection_name: str = "products", db_name: str = "watchvine_refined"):
        """Initialize Gemini Vector Search"""
        # Configure Gemini API
        genai.configure(api_key=google_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # MongoDB setup with Stable API for Atlas
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
        self.collection = self.db[collection_name]
        
        # Check if we're using Atlas (vector search available) or local MongoDB
        self.is_atlas = self._check_if_atlas()
        
        if self.is_atlas:
            # Create vector search index if not exists
            self._create_vector_index()
            logging.info("Gemini Vector Search initialized (Atlas mode)")
        else:
            # Create text index for local MongoDB
            self._create_text_index()
            logging.info("Gemini Vector Search initialized (Local MongoDB mode - using text search fallback)")
    
    def _check_if_atlas(self) -> bool:
        """Check if connected to MongoDB Atlas (supports vector search)"""
        try:
            # Try to list search indexes - only works on Atlas
            list(self.collection.list_search_indexes())
            return True
        except Exception:
            return False
    
    def _create_text_index(self):
        """Create text index for local MongoDB fallback"""
        try:
            # Create text index on searchable_text field
            existing_indexes = self.collection.list_indexes()
            has_text_index = any(
                idx.get('key', {}).get('searchable_text') == 'text' 
                for idx in existing_indexes
            )
            
            if not has_text_index:
                self.collection.create_index([
                    ('searchable_text', 'text'),
                    ('name', 'text'),
                    ('brand', 'text')
                ])
                logging.info("Text search index created for local MongoDB")
        except Exception as e:
            logging.warning(f"Text index creation: {e}")
    
    def _create_vector_index(self):
        """Create vector search index in MongoDB Atlas"""
        try:
            # Create vector search index for embeddings
            index_definition = {
                "mappings": {
                    "dynamic": True,
                    "fields": {
                        "text_embedding": {
                            "type": "knnVector",
                            "dimensions": 768,  # Gemini embedding dimension
                            "similarity": "cosine"
                        }
                    }
                }
            }
            
            # Check if index exists
            existing_indexes = list(self.collection.list_search_indexes())
            if not any(idx.get('name') == 'vector_index' for idx in existing_indexes):
                self.collection.create_search_index(
                    index_definition, 
                    name="vector_index"
                )
                logging.info("Vector search index created")
        except Exception as e:
            logging.warning(f"Vector index creation: {e}")
    
    def generate_text_embedding(self, text: str) -> List[float]:
        """Generate text embedding using Gemini"""
        try:
            # Use Gemini embedding model
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_query",
                output_dimensionality=768
            )
            return result['embedding']
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            return []
    
    def create_searchable_text(self, product: Dict) -> str:
        """Create comprehensive searchable text for product"""
        text_parts = [
            product.get('name', ''),
            product.get('brand', ''),
            product.get('category', ''),
            product.get('description', ''),
            ' '.join(product.get('colors', [])),
            ' '.join(product.get('styles', [])),
            ' '.join(product.get('materials', [])),
            product.get('belt_type', '').replace('_', ' '),
            product.get('ai_category', '').replace('_', ' '),
            product.get('ai_gender_target', ''),
            product.get('price_range', ''),
            f"price {product.get('price', '0')} rupees"
        ]
        
        # Add AI analysis details
        if 'ai_analysis' in product:
            details = product['ai_analysis'].get('additional_details', {})
            text_parts.extend([
                details.get('dial_color', ''),
                details.get('strap_material', ''),
                details.get('watch_type', ''),
                details.get('case_material', ''),
                ' '.join(details.get('design_elements', []))
            ])
        
        return ' '.join(filter(None, text_parts)).lower()
    
    def index_products(self, batch_size: int = 50):
        """Index all products with embeddings"""
        logging.info("Starting product indexing...")
        
        # Get products without embeddings
        unindexed_query = {"text_embedding": {"$exists": False}}
        products = list(self.collection.find(unindexed_query))
        
        if not products:
            logging.info("All products already indexed")
            return
        
        logging.info(f"Indexing {len(products)} products...")
        
        indexed_count = 0
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            for product in batch:
                try:
                    # Create searchable text
                    searchable_text = self.create_searchable_text(product)
                    
                    # Generate embedding
                    embedding = self.generate_text_embedding(searchable_text)
                    
                    if embedding:
                        # Update product with embedding
                        self.collection.update_one(
                            {"_id": product["_id"]},
                            {
                                "$set": {
                                    "text_embedding": embedding,
                                    "searchable_text": searchable_text,
                                    "indexed_at": datetime.now().isoformat()
                                }
                            }
                        )
                        indexed_count += 1
                    
                    time.sleep(0.1)  # Rate limiting
                    
                except Exception as e:
                    logging.error(f"Error indexing product {product.get('name')}: {e}")
            
            logging.info(f"Indexed {min(i + batch_size, len(products))}/{len(products)} products")
            time.sleep(1)  # Batch delay
        
        logging.info(f"Indexing complete. Indexed {indexed_count} products")
    
    def vector_search(self, query: str, limit: int = 5) -> List[Dict]:
        """Perform vector search using query (or text search fallback for local MongoDB)"""
        try:
            if self.is_atlas:
                # Use vector search for Atlas
                return self._vector_search_atlas(query, limit)
            else:
                # Use text search for local MongoDB
                return self._text_search_local(query, limit)
            
        except Exception as e:
            logging.error(f"Search error: {e}")
            return []
    
    def _vector_search_atlas(self, query: str, limit: int) -> List[Dict]:
        """Perform vector search on MongoDB Atlas"""
        try:
            # Generate query embedding
            query_embedding = self.generate_text_embedding(query)
            
            if not query_embedding:
                return []
            
            # MongoDB vector search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "text_embedding",
                        "queryVector": query_embedding,
                        "numCandidates": 100,
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "name": 1,
                        "brand": 1,
                        "price": 1,
                        "image_urls": 1,
                        "url": 1,
                        "colors": 1,
                        "styles": 1,
                        "materials": 1,
                        "belt_type": 1,
                        "ai_category": 1,
                        "ai_gender_target": 1,
                        "description": 1,
                        "category": 1,
                        "category_key": 1,
                        "gender": 1,
                        "price_range": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            
            results = list(self.collection.aggregate(pipeline))
            
            # --- HYBRID RE-RANKING ---
            # Boost scores if the query keyword actually appears in Brand or Name
            # This fixes the issue where "Rolex" vector is similar to "Rado" vector
            query_lower = query.lower()
            keywords = query_lower.split()
            
            for result in results:
                # Base vector score (usually 0.6 to 0.9)
                vector_score = result.get('score', 0)
                
                # Keyword boost
                keyword_score = 0
                name = result.get('name', '').lower()
                brand = result.get('brand', '').lower() if result.get('brand') else ''
                searchable = result.get('searchable_text', '').lower()
                
                # Check for exact brand match (High priority)
                if query_lower in brand:
                    keyword_score += 0.5  # Huge boost for brand match
                
                # Check for keyword occurrences
                for keyword in keywords:
                    if keyword in brand:
                        keyword_score += 0.2
                    if keyword in name:
                        keyword_score += 0.1
                
                # Combined score
                result['score'] = vector_score + keyword_score
            
            # Re-sort by new hybrid score
            results.sort(key=lambda x: x.get('score', 0), reverse=True)

            return results
            
        except Exception as e:
            logging.error(f"Vector search error: {e}")
            return []
    
    def _text_search_local(self, query: str, limit: int, filters: Dict = None) -> List[Dict]:
        """Perform text-based search on local MongoDB"""
        try:
            query_lower = query.lower()
            
            # Split query into keywords for better matching
            keywords = query_lower.split()
            
            # Build regex search (cannot combine $text with $or containing regex)
            regex_conditions = []
            
            for keyword in keywords:
                regex_pattern = {"$regex": keyword, "$options": "i"}
                regex_conditions.append({
                    "$or": [
                        {"name": regex_pattern},
                        {"brand": regex_pattern},
                        {"searchable_text": regex_pattern},
                        {"category": regex_pattern},
                        {"colors": {"$in": [keyword, keyword.title(), keyword.upper()]}},
                        {"styles": {"$in": [keyword, keyword.title(), keyword.upper()]}},
                        {"materials": {"$in": [keyword, keyword.title(), keyword.upper()]}}
                    ]
                })
            
            # Combine keyword conditions (must match at least one keyword)
            if len(regex_conditions) > 1:
                match_stage = {"$and": regex_conditions}
            else:
                match_stage = regex_conditions[0] if regex_conditions else {}
            
            # Add filters if provided
            if filters:
                filter_conditions = [match_stage] if match_stage else []
                
                if filters.get('colors'):
                    filter_conditions.append({"colors": {"$in": filters['colors']}})
                if filters.get('brand'):
                    filter_conditions.append({"brand": {"$regex": filters['brand'], "$options": "i"}})
                if filters.get('min_price'):
                    filter_conditions.append({"price": {"$gte": str(filters['min_price'])}})
                if filters.get('max_price'):
                    filter_conditions.append({"price": {"$lte": str(filters['max_price'])}})
                if filters.get('belt_type'):
                    filter_conditions.append({"belt_type": filters['belt_type']})
                if filters.get('category_key'):
                    filter_conditions.append({"category_key": filters['category_key']})
                if filters.get('gender'):
                    filter_conditions.append({"gender": {"$regex": filters['gender'], "$options": "i"}})
                
                if len(filter_conditions) > 1:
                    match_stage = {"$and": filter_conditions}
                elif filter_conditions:
                    match_stage = filter_conditions[0]
            
            # Execute search
            if not match_stage:
                # If no conditions, return all products with limit
                match_stage = {}
            
            results = list(self.collection.find(
                match_stage,
                {
                    "name": 1,
                    "brand": 1,
                    "price": 1,
                    "image_urls": 1,
                    "url": 1,
                    "colors": 1,
                    "styles": 1,
                    "materials": 1,
                    "belt_type": 1,
                    "category": 1,
                    "category_key": 1,
                    "gender": 1,
                    "price_range": 1,
                    "searchable_text": 1,
                    "ai_analysis": 1
                }
            ).limit(limit))
            
            # Add scoring based on keyword matches
            for result in results:
                score = 0
                name = result.get('name', '').lower()
                brand = result.get('brand', '').lower() if result.get('brand') else ''
                searchable = result.get('searchable_text', '').lower()
                
                # Score based on how many keywords match
                for keyword in keywords:
                    if keyword in name:
                        score += 10
                    if keyword in brand:
                        score += 7
                    if keyword in searchable:
                        score += 3
                
                # Bonus if query matches exactly
                if query_lower in name:
                    score += 20
                if query_lower in brand:
                    score += 15
                
                result['score'] = score
            
            # Sort by score (higher is better)
            results.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            logging.info(f"Text search found {len(results)} results for '{query}'")
            return results
            
        except Exception as e:
            logging.error(f"Text search error: {e}")
            return []
    
    def hybrid_search(self, query: str, filters: Dict = None, limit: int = 5) -> List[Dict]:
        """Combine vector search with traditional filters (or text search for local MongoDB)"""
        try:
            if self.is_atlas:
                # Use vector search with filters for Atlas
                return self._hybrid_search_atlas(query, filters, limit)
            else:
                # Use text search with filters for local MongoDB
                return self._text_search_local(query, limit, filters)
            
        except Exception as e:
            logging.error(f"Hybrid search error: {e}")
            return []
    
    def _hybrid_search_atlas(self, query: str, filters: Dict = None, limit: int = 5) -> List[Dict]:
        """Combine vector search with traditional filters on MongoDB Atlas"""
        try:
            # Generate query embedding
            query_embedding = self.generate_text_embedding(query)
            
            if not query_embedding:
                return []
            
            # Build filter stage
            match_stage = {}
            if filters:
                if filters.get('colors'):
                    match_stage['colors'] = {"$in": filters['colors']}
                if filters.get('brand'):
                    match_stage['brand'] = {"$regex": filters['brand'], "$options": "i"}
                if filters.get('min_price'):
                    match_stage['price'] = {"$gte": str(filters['min_price'])}
                if filters.get('max_price'):
                    if 'price' in match_stage:
                        match_stage['price']['$lte'] = str(filters['max_price'])
                    else:
                        match_stage['price'] = {"$lte": str(filters['max_price'])}
                if filters.get('belt_type'):
                    match_stage['belt_type'] = filters['belt_type']
                if filters.get('category_key'):
                    match_stage['category_key'] = filters['category_key']
                if filters.get('gender'):
                    match_stage['gender'] = {"$regex": filters['gender'], "$options": "i"}
            
            # Build pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "text_embedding",
                        "queryVector": query_embedding,
                        "numCandidates": 200,
                        "limit": limit * 3  # Get more candidates for filtering
                    }
                }
            ]
            
            # Add filter stage if filters exist
            if match_stage:
                pipeline.append({"$match": match_stage})
            
            # Project and limit
            pipeline.extend([
                {
                    "$project": {
                        "name": 1,
                        "brand": 1,
                        "price": 1,
                        "image_urls": 1,
                        "url": 1,
                        "colors": 1,
                        "styles": 1,
                        "materials": 1,
                        "belt_type": 1,
                        "category": 1,
                        "category_key": 1,
                        "gender": 1,
                        "price_range": 1,
                        "description": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                },
                {"$limit": limit}
            ])
            
            results = list(self.collection.aggregate(pipeline))
            return results
            
        except Exception as e:
            logging.error(f"Hybrid search error: {e}")
            return []
    
    def get_indexing_stats(self) -> Dict:
        """Get indexing statistics"""
        total_products = self.collection.count_documents({})
        indexed_products = self.collection.count_documents({"text_embedding": {"$exists": True}})
        
        return {
            "total_products": total_products,
            "indexed_products": indexed_products,
            "indexing_percentage": (indexed_products / max(total_products, 1)) * 100
        }
    
    def close(self):
        """Close database connection"""
        self.client.close()

# Test function
if __name__ == "__main__":
    MONGODB_URI = "mongodb://admin:strongpassword123@72.62.76.36:27017/?authSource=admin"
    GOOGLE_API_KEY = ""
    
    search = GeminiVectorSearch(MONGODB_URI, GOOGLE_API_KEY)
    
    # Test search
    results = search.vector_search("black luxury watch")
    print(f"Found {len(results)} results")
    
    for result in results:
        print(f"- {result.get('name')} (Score: {result.get('score', 0):.3f})")
    
    search.close()