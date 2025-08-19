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


async def fetch_latest_video():
    """Devuelve (video_id, title, url, published) del video más reciente, o None si no hay."""
    async with http_session.get(RSS_URL, timeout=20) as r:
        r.raise_for_status()
        text = await r.text()

    feed = feedparser.parse(text)
    if not feed.entries:
        return None

    e = feed.entries[0]
    video_id = (e.get("yt_videoid") or e.get("id") or "").split(":")[-1]
    title = e.get("title", "Nuevo video")
    link = e.get("link", f"https://www.youtube.com/watch?v={video_id}")
    published = e.get("published", "")
    return video_id, title, link, published
