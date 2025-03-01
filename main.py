import os
import re
import asyncio
import logging
from threading import Thread
from telethon import TelegramClient, events
from deep_translator import GoogleTranslator
from flask import Flask
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("RailwayBot")

class Config:
    API_ID = int(os.getenv("API_ID", 27005697))
    API_HASH = os.getenv("API_HASH", "a139f9146e1ee53af2309a5b000ec053")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7820965716:AAEjPRHFA74dqhS8ZgmG7IQKpWbaHnFVaEU")
    TARGET_CHANNEL = os.getenv("TARGET_CHANNEL", "@whaleguardian")
    SOURCE_CHANNELS = list(filter(None, os.getenv("SOURCE_CHANNELS", "cryptoquant_alert,whale_alert_io,glassnode,cryptoquant_official,AI_Iman").split(",")))

    @classmethod
    def validate(cls):
        required = {
            "API_ID": cls.API_ID,
            "API_HASH": cls.API_HASH,
            "BOT_TOKEN": cls.BOT_TOKEN,
            "TARGET_CHANNEL": cls.TARGET_CHANNEL,
            "SOURCE_CHANNELS": cls.SOURCE_CHANNELS
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            logger.error(f"Missing configuration: {', '.join(missing)}")
            exit(1)

Config.validate()

# Telegram client setup
client = TelegramClient("railway_session", Config.API_ID, Config.API_HASH).start(bot_token=Config.BOT_TOKEN)

# Translation function with proper URL handling
def translate_text(text: str) -> str:
    try:
        url_placeholders = {}
        for i, url in enumerate(re.findall(r'https?://\S+', text)):
            placeholder = f"URL_{i}"
            text = text.replace(url, placeholder)
            url_placeholders[placeholder] = url
        
        translated = GoogleTranslator(source='auto', target='fa').translate(text)
        
        for placeholder, url in url_placeholders.items():
            translated = translated.replace(placeholder, url)
        
        return translated
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text

async def handle_media_message(event):
    try:
        # Send media first
        media_msg = await client.send_file(
            Config.TARGET_CHANNEL,
            event.message.media
        )
        
        # Process caption separately
        if event.message.text:
            translated = translate_text(event.message.text)
            await client.send_message(
                Config.TARGET_CHANNEL,
                f"{translated}\n\n@whaleguardian",
                reply_to=media_msg.id
            )
    except Exception as e:
        logger.error(f"Media handling error: {e}")

@client.on(events.NewMessage(chats=Config.SOURCE_CHANNELS))
async def message_handler(event):
    try:
        if event.message.media:
            await handle_media_message(event)
        elif event.message.text:
            translated = translate_text(event.message.text)
            await client.send_message(
                Config.TARGET_CHANNEL,
                f"{translated}\n\n@whaleguardian"
            )
    except Exception as e:
        logger.error(f"Handler error: {e}")

# Flask keep-alive server
app = Flask(__name__)

@app.route("/")
def health_check():
    return "Bot is running"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    logger.info("Starting Telegram bot...")
    client.run_until_disconnected()
