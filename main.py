import os
import re
import asyncio
import logging
from threading import Thread
from datetime import datetime
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message
from deep_translator import GoogleTranslator
from flask import Flask
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure minimal logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("TgTransBot")

class Config:
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    PHONE = os.getenv("PHONE", "")
    SOURCE_CHANNELS = list(filter(None, os.getenv("SOURCE_CHANNELS", "").split(",")))
    TARGET_CHANNEL = os.getenv("TARGET_CHANNEL", "")
    FOOTER = os.getenv("FOOTER_TEXT", "\n\n@whaleguardian")
    MAX_TASKS = 3  # Conservative concurrency limit

    @classmethod
    def validate(cls):
        required = {
            'API_ID': cls.API_ID,
            'API_HASH': cls.API_HASH,
            'PHONE': cls.PHONE,
            'TARGET_CHANNEL': cls.TARGET_CHANNEL,
            'SOURCE_CHANNELS': cls.SOURCE_CHANNELS
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.error(f"Missing config: {', '.join(missing)}")
            exit(1)

Config.validate()

# Telegram Client Setup
client = TelegramClient(
    session=datetime.now().strftime("session_%H%M"),
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    system_version="4.16.30-v3"
)

class Translator:
    URL_REGEX = re.compile(r'https?://\S+|www\.\S+')
    SEM = asyncio.Semaphore(Config.MAX_TASKS)

    @classmethod
    async def translate(cls, text: str) -> str:
        async with cls.SEM:
            try:
                # Preserve URLs during translation
                urls = cls.URL_REGEX.findall(text)
                text = cls.URL_REGEX.sub(" URL_PLACEHOLDER ", text)
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target='fa').translate,
                    text[:4000]  # Limit input size
                )
                # Restore URLs
                for url in urls:
                    translated = translated.replace("URL_PLACEHOLDER", url, 1)
                return translated
            except Exception as e:
                logger.warning(f"Translation skipped: {str(e)}")
                return text

async def send_caption_reply(media_msg: Message, text: str):
    """Send translated caption as reply to media message"""
    try:
        translated = await Translator.translate(text)
        await client.send_message(
            Config.TARGET_CHANNEL,
            f"{translated}{Config.FOOTER}",
            reply_to=media_msg.id
        )
    except Exception as e:
        logger.error(f"Caption failed: {str(e)}")

@client.on(events.NewMessage(chats=Config.SOURCE_CHANNELS))
async def message_handler(event: events.NewMessage.Event):
    """Resource-optimized message handler"""
    try:
        msg = event.message
        
        # Handle media first
        if msg.media:
            media_msg = await client.send_file(
                Config.TARGET_CHANNEL,
                msg.media,
                caption=msg.text or None  # Original caption if exists
            )
            
            # Process caption in background if present
            if msg.text:
                asyncio.create_task(send_caption_reply(media_msg, msg.text))

        # Handle text-only messages
        elif msg.text:
            translated = await Translator.translate(msg.text)
            await client.send_message(
                Config.TARGET_CHANNEL,
                f"{translated}{Config.FOOTER}"
            )

    except Exception as e:
        logger.error(f"Handler error: {str(e)}")

# Minimal keep-alive server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Active"

def run_server():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

async def main():
    await client.start(phone=Config.PHONE)
    logger.info(f"Connected as User#{await client.get_me().id}")
    await client.run_until_disconnected()

if __name__ == '__main__':
    # Start lightweight server
    Thread(target=run_server, daemon=True).start()
    
    # Run with cleanup
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Graceful shutdown")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        client.loop.stop()
        logger.info("Resources cleaned")
