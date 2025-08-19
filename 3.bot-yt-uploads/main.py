import os
import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord.ext import tasks
from dotenv import load_dotenv
import feedparser

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANNOUNCE_CHANNEL_ID = int(os.getenv("ANNOUNCE_CHANNEL_ID", "0"))
YT_CHANNEL_ID = os.getenv("YT_CHANNEL_ID", "").strip()
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("yt-upload-bot")

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL_ID}"

state_last_video_id: Optional[str] = None
http_session: Optional[aiohttp.ClientSession] = None
