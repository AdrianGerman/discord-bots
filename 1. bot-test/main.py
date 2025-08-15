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


@bot.command()
async def poke(ctx, arg):
    try:
        arg.split(" ", 1)[0].lower()
        result = requests.get(f"https://pokeapi.co/api/v2/pokemon/{arg}")
        if result.text == "Not Found":
            await ctx.send("Pokemon no encontrado :(.")
        else:
            image_url = result.json()["sprites"]["front_default"]
            print(image_url)
            await ctx.send(image_url)
    except Exception as e:
        print(f"Error: {e}")


@poke.error
async def error_type(ctx, error):
    if isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send("Por favor, ingresa el nombre del pokemon que quieres buscar.")


@bot.event
async def on_ready():
    print(f"Estamos dentro! {bot.user}")


@bot.command()
async def clean(ctx):
    await ctx.channel.purge(limit=100)
    await ctx.send("Limpieza completa! :broom:", delete_after=5)


bot.run(secret.TOKEN)
