import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
import threading
import base64
import json
from datetime import datetime, timezone
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return {"its all good here man"}

@app.get("/v2/token")
async def get_token():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://femboys.quest/s") as resp:
            data = await resp.json()
    return data

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

TOKEN = os.environ.get("BOT_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


@bot.tree.command(name="tok", description="idk what to put here")
async def token(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://femboys.quest/s") as resp:
                data = await resp.json()

        bearer = data.get("bearer", "N/A")
        refresh = data.get("refresh", "N/A")

        msg = (
            f"heres your token lol have fun\n\n"
            f"**Token:**\n```\n{bearer}\n```\n"
            f"**Refresh:**\n```\n{refresh}\n```"
        )
        try:
            dm = await interaction.user.create_dm()
            await dm.send(msg)
            await interaction.followup.send("Check DMs", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}", ephemeral=True)


def decode_jwt(token_str):
    try:
        payload = token_str.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        payload = payload.replace('-', '+').replace('_', '/')
        return json.loads(base64.b64decode(payload))
    except Exception:
        return {}


@bot.tree.command(name="tokcheck", description="Get a token and see exactly when it expires")
async def tokcheck(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://femboys.quest/s") as resp:
                data = await resp.json()

        bearer = data.get("bearer", "N/A")
        refresh = data.get("refresh", "N/A")

        bearer_data = decode_jwt(bearer)
        refresh_data = decode_jwt(refresh)

        bearer_exp = datetime.fromtimestamp(bearer_data.get("exp", 0), tz=timezone.utc)
        refresh_exp = datetime.fromtimestamp(refresh_data.get("exp", 0), tz=timezone.utc)

        bearer_id = bearer_data.get("uid", "N/A")
        username = bearer_data.get("usn", "N/A")

        msg = (
            f"**Username:** `{username}`\n"
            f"**UID:** `{bearer_id}`\n\n"
            f"**Bearer Token Expires:** <t:{int(bearer_exp.timestamp())}:R> (`{bearer_exp.strftime('%Y-%m-%d %H:%M:%S UTC')}`)\n"
            f"**Refresh Token Expires:** <t:{int(refresh_exp.timestamp())}:R> (`{refresh_exp.strftime('%Y-%m-%d %H:%M:%S UTC')}`)\n\n"
            f"**Token:**\n```\n{bearer}\n```\n"
            f"**Refresh:**\n```\n{refresh}\n```"
        )
        try:
            dm = await interaction.user.create_dm()
            await dm.send(msg)
            await interaction.followup.send("Check DMs", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}", ephemeral=True)


web_thread = threading.Thread(target=run_web, daemon=True)
web_thread.start()

bot.run(TOKEN)
