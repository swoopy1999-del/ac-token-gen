import os
import json
import base64
import threading
import discord
from discord import app_commands
import requests
import jwt
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_URL = "https://animalcompany.us-east1.nakamacloud.io"
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
SERVER_KEY = os.environ.get("SERVER_KEY", "6URuTSlDKKfYbuDW")

token_store = {"token": "", "refresh": ""}

def load_tokens():
    if os.path.exists("auth.json"):
        with open("auth.json", "r") as f:
            data = json.load(f)
            token_store["token"] = data.get("token", "")
            token_store["refresh"] = data.get("refresh", "")

def save_tokens():
    with open("auth.json", "w") as f:
        json.dump(token_store, f, indent=2)

def refresh_token():
    refresh = token_store.get("refresh")
    if not refresh:
        return None, None
    encoded = base64.b64encode(f"{SERVER_KEY}:".encode()).decode()
    resp = requests.post(
        f"{BASE_URL}/v2/account/session/refresh",
        json={"token": refresh},
        headers={"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}
    )
    if resp.status_code == 200:
        data = resp.json()
        token_store["token"] = data.get("token", token_store["token"])
        if "refresh" in data:
            token_store["refresh"] = data["refresh"]
        save_tokens()
        return token_store["token"], token_store["refresh"]
    return None, None

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"logged in as {bot.user}")

@tree.command(name="tok", description="Refresh and get your Animal Company token")
async def tok(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    token, refresh = refresh_token()
    if token:
        try:
            await interaction.user.send(f"**Bearer Token:**\n```\n{token}\n```\n**Refresh Token:**\n```\n{refresh}\n```")
            await interaction.followup.send("Sent you a DM with your tokens.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("Couldn't DM you. Enable DMs and try again.", ephemeral=True)
    else:
        await interaction.followup.send("Failed to refresh token.", ephemeral=True)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass

def run_web():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8000))), Handler).serve_forever()

if __name__ == "__main__":
    load_tokens()
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(DISCORD_TOKEN)
