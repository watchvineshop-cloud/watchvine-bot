"""
WhatsApp Helper Module - Simplified
Handles sending messages and media through Evolution API
"""

import os
import requests
import logging
import time
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Evolution API Configuration
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "shop-bot")

HEADERS = {
    "apikey": EVOLUTION_API_KEY,
    "Content-Type": "application/json"
}

def clean_phone_number(phone_number: str) -> str:
    """Clean and format phone number"""
    phone = phone_number.replace("+", "").replace("-", "").replace(" ", "")
    if len(phone) == 10:
        phone = "91" + phone
    return phone

def send_whatsapp_message(phone_number: str, message: str, max_retries: int = 3) -> bool:
    """Send a text message via Evolution API with retry logic"""
    phone = clean_phone_number(phone_number)
    url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    
    payload = {
        "number": phone,
        "text": message
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=15)
            if response.status_code in [200, 201]:
                logger.info(f"✅ Message sent to {phone_number}")
                return True
            else:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt + 1} error: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(1)
    
    logger.error(f"❌ Failed to send message after {max_retries} attempts")
    return False

def send_whatsapp_media(phone_number: str, media_url: str, caption: str = "", media_type: str = "image", max_retries: int = 3) -> bool:
    """Send media (image/video) via Evolution API using URL"""
    phone = clean_phone_number(phone_number)
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{INSTANCE_NAME}"
    
    payload = {
        "number": phone,
        "mediatype": media_type,
        "media": media_url,
        "caption": caption
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=20)
            if response.status_code in [200, 201]:
                logger.info(f"✅ {media_type.capitalize()} sent to {phone_number}")
                return True
            else:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt + 1} error: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(1)
    
    logger.error(f"❌ Failed to send {media_type} after {max_retries} attempts")
    return False
