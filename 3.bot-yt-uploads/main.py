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


@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def check_youtube():
    global state_last_video_id
    if not ANNOUNCE_CHANNEL_ID or not YT_CHANNEL_ID:
        return

    try:
        latest = await fetch_latest_video()
    except Exception as e:
        log.warning(f"Error leyendo feed de YouTube: {e}")
        return

    if not latest:
        return

    video_id, title, link, published = latest

    # Primera ejecución: memoriza el último video y no anuncies (para no spamear con videos antiguos).
    if state_last_video_id is None:
        state_last_video_id = video_id
        log.info(f"Inicializado con último video {video_id}")
        return

    if video_id != state_last_video_id:
        state_last_video_id = video_id
        ch = bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if ch:
            embed = discord.Embed(
                title=title,
                description=f"¡Nuevo video en el canal! 🎬\n{link}",
            )
            # Miniatura estándar de YouTube:
            thumb = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            embed.set_thumbnail(url=thumb)
            embed.add_field(
                name="Publicado", value=published or "hace poco", inline=True
            )
            await ch.send(embed=embed)
            log.info(f"Anunciado video nuevo: {video_id}")


@check_youtube.before_loop
async def before_loop():
    await bot.wait_until_ready()
    log.info("Iniciando tarea check_youtube...")


@bot.event
async def on_ready():
    log.info(f"Conectado como {bot.user} (latency {bot.latency*1000:.0f}ms)")
    if not check_youtube.is_running():
        check_youtube.start()


async def main():
    global http_session
    http_session = aiohttp.ClientSession()
    try:
        await bot.start(BOT_TOKEN)
    finally:
        await http_session.close()


if __name__ == "__main__":
    asyncio.run(main())
