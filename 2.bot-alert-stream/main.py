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

    async def get_stream(self, user_login: str) -> Optional[dict]:
        """Devuelve dict con datos del stream si está en vivo; None si está offline."""
        await self.ensure_token()
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self._app_token}",
        }
        params = {"user_login": user_login}
        url = "https://api.twitch.tv/helix/streams"
        async with self.session.get(
            url, headers=headers, params=params, timeout=20
        ) as r:
            if r.status == 401:
                # Token expirado → refrescar y reintentar una vez
                await self.refresh_token()
                headers["Authorization"] = f"Bearer {self._app_token}"
                async with self.session.get(
                    url, headers=headers, params=params, timeout=20
                ) as r2:
                    r2.raise_for_status()
                    js2 = await r2.json()
                    data = js2.get("data", [])
                    return data[0] if data else None
            r.raise_for_status()
            js = await r.json()
            data = js.get("data", [])
            return data[0] if data else None

    async def get_user(self, user_login: str) -> Optional[dict]:
        await self.ensure_token()
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self._app_token}",
        }
        params = {"login": user_login}
        url = "https://api.twitch.tv/helix/users"
        async with self.session.get(
            url, headers=headers, params=params, timeout=20
        ) as r:
            r.raise_for_status()
            js = await r.json()
            data = js.get("data", [])
            return data[0] if data else None


# ----------------- State -----------------
class StreamState:
    def __init__(self):
        self.live = False
        self.stream_id: Optional[str] = (
            None  # para evitar duplicados en el mismo directo
        )


state = StreamState()
http_session: aiohttp.ClientSession | None = None
twitch: TwitchClient | None = None


# ----------------- Tasks -----------------
@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def check_twitch():
    if not twitch or not TWITCH_USER_LOGIN or not ANNOUNCE_CHANNEL_ID:
        return

    try:
        stream = await twitch.get_stream(TWITCH_USER_LOGIN)
    except Exception as e:
        log.warning(f"Error checking Twitch: {e}")
        return

    if stream:
        stream_id = stream.get("id")
        title = stream.get("title", "¡En directo!")
        game_name = stream.get("game_name", "")
        thumbnail_url = stream.get("thumbnail_url", "")
        viewer_count = stream.get("viewer_count", 0)
        url = f"https://twitch.tv/{TWITCH_USER_LOGIN}"

        if not state.live or state.stream_id != stream_id:
            # se acaba de iniciar un directo (o nuevo id por reinicio)
            state.live = True
            state.stream_id = stream_id

            channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
            if channel:
                mention = f"<@&{ANNOUNCE_ROLE_ID}>" if ANNOUNCE_ROLE_ID else ""
                embed = discord.Embed(
                    title=title,
                    description=f"{TWITCH_USER_LOGIN} está **en directo** {(f'jugando a {game_name}' if game_name else '')}.\n\n**¡Entra!** → {url}",
                )
                embed.add_field(name="Viewers", value=str(viewer_count))
                if thumbnail_url:
                    # reemplaza dimensiones por 1280x720 para obtener una imagen
                    embed.set_image(
                        url=thumbnail_url.replace("{width}", "1280").replace(
                            "{height}", "720"
                        )
                    )

                await channel.send(
                    content=f"{mention} 📣 ¡Directo iniciado!", embed=embed
                )
                log.info("Anuncio enviado.")
    else:
        if state.live:
            # Se acaba de terminar el directo
            state.live = False
            state.stream_id = None
            channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
            if channel:
                await channel.send("🔴 El directo ha terminado. ¡Gracias por pasarte!")
                log.info("Mensaje de fin enviado.")


@check_twitch.before_loop
async def before_check():
    await bot.wait_until_ready()
    log.info("check_twitch task starting...")
