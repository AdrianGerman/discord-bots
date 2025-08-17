import os
import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord.ext import tasks
from dotenv import load_dotenv

# ----------------- Config & Logging -----------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANNOUNCE_CHANNEL_ID = int(os.getenv("ANNOUNCE_CHANNEL_ID", "0"))
ANNOUNCE_ROLE_ID = int(os.getenv("ANNOUNCE_ROLE_ID", "0"))

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USER_LOGIN = (os.getenv("TWITCH_USER_LOGIN") or "").lower()

CHECK_INTERVAL_SECONDS = int(
    os.getenv("CHECK_INTERVAL_SECONDS", "60")
)  # 60–120s es razonable (lo podemos cambiar en el futuro, viendo como va funcionando).


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("stream-alert-bot")

# ----------------- Discord Setup -----------------

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)


# ----------------- Twitch Client -----------------
class TwitchClient:
    def __init__(
        self, client_id: str, client_secret: str, session: aiohttp.ClientSession
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = session
        self._app_token: Optional[str] = None
        self._token_type: Optional[str] = None

    async def ensure_token(self):
        if self._app_token is None:
            await self.refresh_token()

    async def refresh_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        async with self.session.post(url, data=data, timeout=20) as r:
            r.raise_for_status()
            js = await r.json()
            self._app_token = js["access_token"]
            self._token_type = js.get("token_type", "bearer")
            log.info("Twitch app token refreshed.")
