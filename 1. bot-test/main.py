import discord
from discord.ext import commands
import requests
import secret  # env variable from secrets file

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.command()
async def test(ctx, *arg):
    await ctx.send(" ".join(arg))


@bot.event
async def on_ready():
    print(f"Estamos dentro! {bot.user}")


bot.run(secret.TOKEN)
