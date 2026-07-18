import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
import threading
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

@app.get("/v2/token/{username}")
async def get_token_by_user(username: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://femboys.quest/s?usn={username}") as resp:
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


@bot.tree.command(name="tokuser", description="Generate token for a specific username")
@app_commands.describe(username="The username to generate a token for")
async def tokuser(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://femboys.quest/s?usn={username}") as resp:
                data = await resp.json()

        bearer = data.get("bearer", "N/A")
        refresh = data.get("refresh", "N/A")

        msg = (
            f"heres your token for **{username}**\n\n"
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
