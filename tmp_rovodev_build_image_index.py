#!/usr/bin/env python3
"""
Build FAISS index for image search
This script needs to run inside the image_identifier container
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Image identifier service URL
IMAGE_IDENTIFIER_URL = os.getenv("IMAGE_IDENTIFIER_URL", "http://watchvine_image_identifier:8002")

print("=" * 80)
print("🔨 Building FAISS Index for Image Search")
print("=" * 80)

try:
    # Call the index builder endpoint
    print("\n📊 Calling index builder...")
    response = requests.post(
        f"{IMAGE_IDENTIFIER_URL}/build_index",
        timeout=300  # 5 minutes timeout
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Index built successfully!")
        print(f"   Total products indexed: {result.get('total_products', 'N/A')}")
        print(f"   Index size: {result.get('index_size', 'N/A')}")
    else:
        print(f"\n❌ Failed to build index: {response.status_code}")
        print(f"   Response: {response.text}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 The image identifier service might not have a /build_index endpoint.")
    print("   You need to manually trigger index building in the container.")
    print("\n   Run this command:")
    print("   docker exec watchvine_image_identifier python -c 'from indexer import build_index; build_index()'")

print("\n" + "=" * 80)
