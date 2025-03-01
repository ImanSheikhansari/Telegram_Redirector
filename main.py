import os
import re
import asyncio
import logging
from threading import Thread
from datetime import datetime

from telethon import TelegramClient, events
from deep_translator import GoogleTranslator
from flask import Flask
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure minimal logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("LowResourceBot")

class ResourceManager:
    MAX_TASKS = 2  # Limit concurrent tasks
    TRANSLATION_TIMEOUT = 15  # Seconds
    URL_REGEX = re.compile(r'https?://\S+')
    
    @classmethod
    def get_env(cls, name: str, default: str = "") -> str:
        return os.getenv(name, default).strip()

class TelegramConfig:
    API_ID = int(ResourceManager.get_env("API_ID", "0"))
    API_HASH = ResourceManager.get_env("API_HASH")
    PHONE = ResourceManager.get_env("PHONE")
    SOURCE_CHATS = list(filter(None, ResourceManager.get_env("SOURCE_CHANNELS").split(",")))
    TARGET_CHAT = ResourceManager.get_env("TARGET_CHANNEL")
    
    @classmethod
    def validate(cls):
        required = {
            "API_ID": cls.API_ID,
            "API_HASH": cls.API_HASH,
            "PHONE": cls.PHONE,
            "SOURCE_CHANNELS": cls.SOURCE_CHATS,
            "TARGET_CHANNEL": cls.TARGET_CHAT
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.error(f"Missing config: {missing}")
            exit(1)

TelegramConfig.validate()

# Telegram client setup
client = TelegramClient(
    session="translation_bot_session",
    api_id=TelegramConfig.API_ID,
    api_hash=TelegramConfig.API_HASH
)

async def limited_translate(text: str) -> str:
    """Resource-constrained translation with fallback"""
    try:
        # Preserve URLs during translation
        urls = ResourceManager.URL_REGEX.findall(text)
        text = ResourceManager.URL_REGEX.sub("URL_PLACEHOLDER", text)
        
        translated = await asyncio.wait_for(
            asyncio.to_thread(
                GoogleTranslator(source="auto", target="fa").translate,
                text
            ),
            timeout=ResourceManager.TRANSLATION_TIMEOUT
        )
        
        for i, url in enumerate(urls):
            translated = translated.replace(f"URL_PLACEHOLDER{i+1}", url)
            
        return translated
    except Exception as e:
        logger.warning(f"Translation fallback: {e}")
        return text

async def handle_media_with_caption(event):
    """Optimized media handling with separated caption processing"""
    try:
        # Send media immediately
        media_msg = await client.send_file(
            TelegramConfig.TARGET_CHAT,
            event.message.media
        )
        
        # Process caption in background if exists
        if event.message.text:
            asyncio.create_task(
                process_caption(media_msg, event.message.text)
            
    except Exception as e:
        logger.error(f"Media error: {e}")

async def process_caption(media_msg, caption: str):
    """Background caption processing"""
    try:
        translated = await limited_translate(caption)
        await client.send_message(
            TelegramConfig.TARGET_CHAT,
            f"{translated}\n\n@whaleguardian",
            reply_to=media_msg.id
        )
    except Exception as e:
        logger.error(f"Caption error: {e}")

@client.on(events.NewMessage(chats=TelegramConfig.SOURCE_CHATS))
async def efficient_handler(event):
    """Resource-constrained message handler"""
    try:
        if event.message.media:
            await handle_media_with_caption(event)
        elif event.message.text:
            translated = await limited_translate(event.message.text)
            await client.send_message(
                TelegramConfig.TARGET_CHAT,
                f"{translated}\n\n@whaleguardian"
            )
    except Exception as e:
        logger.error(f"Handler error: {e}")

# Minimal keep-alive server
app = Flask(__name__)

@app.route("/")
def ping():
    return "OK"

def run_server():
    app.run(host="0.0.0.0", port=8080, threaded=True)

async def main():
    await client.start(phone=TelegramConfig.PHONE)
    logger.warning("Bot started in low-resource mode")
    await client.run_until_disconnected()

if __name__ == "__main__":
    # Start lightweight server in background
    Thread(target=run_server, daemon=True).start()
    
    # Configure event loop for resource constraints
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.warning("Graceful shutdown")
    finally:
        loop.close()
