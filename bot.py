import os
import json
import time
import base64
import asyncio
import discord
from discord import app_commands
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import requests
import jwt
import threading

# --- Config ---
BASE_URL = "https://animalcompany.us-east1.nakamacloud.io"
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
SERVER_KEY = os.environ.get("SERVER_KEY", "6URuTSlDKKfYbuDW")
OWNER_ID = os.environ.get("OWNER_ID", "")

# --- Token Store (in-memory, persisted via env/filesystem) ---
token_store = {
    "token": os.environ.get("AC_TOKEN", ""),
    "refresh": os.environ.get("AC_REFRESH", ""),
}

def save_tokens():
    with open("auth.json", "w") as f:
        json.dump(token_store, f, indent=2)

def load_tokens():
    if os.path.exists("auth.json"):
        with open("auth.json", "r") as f:
            data = json.load(f)
            token_store["token"] = data.get("token", "")
            token_store["refresh"] = data.get("refresh", "")

def decode_token(token):
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None

def is_expired(token):
    payload = decode_token(token)
    if not payload:
        return True
    return time.time() >= payload.get("exp", 0)

def refresh_token():
    refresh = token_store.get("refresh")
    if not refresh:
        return None

    encoded = base64.b64encode(f"{SERVER_KEY}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json"
    }

    resp = requests.post(
        f"{BASE_URL}/v2/account/session/refresh",
        json={"token": refresh},
        headers=headers
    )

    if resp.status_code == 200:
        data = resp.json()
        token_store["token"] = data.get("token", token_store["token"])
        if "refresh" in data:
            token_store["refresh"] = data["refresh"]
        save_tokens()
        return token_store["token"]
    return None

def get_token():
    if is_expired(token_store["token"]):
        new = refresh_token()
        if new:
            return new
        return None
    return token_store["token"]

def api_call(method, endpoint, data=None):
    token = get_token()
    if not token:
        return {"error": "no valid token"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}{endpoint}"
    if method.upper() == "GET":
        resp = requests.get(url, headers=headers)
    else:
        resp = requests.post(url, json=data or {}, headers=headers)

    if resp.status_code == 401:
        token = refresh_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers)
            else:
                resp = requests.post(url, json=data or {}, headers=headers)

    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text, "status": resp.status_code}

# --- FastAPI (keeps Render service alive) ---
app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "service": "animal-company-bot"}

@app.get("/health")
def health():
    return {"healthy": True}

@app.get("/tokens")
def get_tokens_status():
    t = token_store["token"]
    payload = decode_token(t) if t else None
    exp = payload.get("exp", 0) if payload else 0
    remaining = max(0, exp - time.time())
    return {
        "has_token": bool(t),
        "has_refresh": bool(token_store["refresh"]),
        "expired": is_expired(t),
        "expires_in_minutes": round(remaining / 60, 1),
    }

# --- Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"[bot] logged in as {bot.user}")

def is_owner():
    if not OWNER_ID:
        return True
    return True

@tree.command(name="ac_status", description="Check Animal Company token status")
async def ac_status(interaction: discord.Interaction):
    t = token_store["token"]
    payload = decode_token(t) if t else None
    exp = payload.get("exp", 0) if payload else 0
    remaining = max(0, exp - time.time())

    embed = discord.Embed(title="Animal Company Token Status", color=0x00ff00 if remaining > 300 else 0xff0000)
    embed.add_field(name="Has Token", value="Yes" if t else "No", inline=True)
    embed.add_field(name="Has Refresh", value="Yes" if token_store["refresh"] else "No", inline=True)
    embed.add_field(name="Expires In", value=f"{remaining/60:.1f} min" if remaining > 0 else "EXPIRED", inline=True)
    await interaction.response.send_message(embed=embed)

@tree.command(name="ac_refresh", description="Force refresh the Animal Company token")
async def ac_refresh(interaction: discord.Interaction):
    await interaction.response.defer()
    new = refresh_token()
    if new:
        await interaction.followup.send("Token refreshed successfully.")
    else:
        await interaction.followup.send("Failed to refresh token.")

@tree.command(name="ac_rpc", description="Call an Animal Company RPC endpoint")
@app_commands.describe(method="GET or POST", rpc="RPC endpoint name")
async def ac_rpc(interaction: discord.Interaction, rpc: str, method: str = "GET"):
    await interaction.response.defer()
    result = api_call(method, f"/v2/rpc/{rpc}")
    text = json.dumps(result, indent=2)
    if len(text) > 1900:
        text = text[:1900] + "\n... (truncated)"
    await interaction.followup.send(f"```json\n{text}\n```")

@tree.command(name="ac_account", description="Get Animal Company account info")
async def ac_account(interaction: discord.Interaction):
    await interaction.response.defer()
    result = api_call("GET", "/v2/account")
    text = json.dumps(result, indent=2)
    await interaction.followup.send(f"```json\n{text}\n```")

@tree.command(name="ac_wallet", description="Get wallet balances (nuts, fishing, mining)")
async def ac_wallet(interaction: discord.Interaction):
    await interaction.response.defer()
    nuts = api_call("GET", "/v2/rpc/nuts.getWallet")
    fishing = api_call("GET", "/v2/rpc/fishing.getWallet")
    mining = api_call("GET", "/v2/rpc/mining.balance")
    embed = discord.Embed(title="Wallet Balances", color=0x00ff00)
    embed.add_field(name="Nuts", value=f"```json\n{json.dumps(nuts, indent=2)}\n```", inline=False)
    embed.add_field(name="Fishing", value=f"```json\n{json.dumps(fishing, indent=2)}\n```", inline=False)
    embed.add_field(name="Mining", value=f"```json\n{json.dumps(mining, indent=2)}\n```", inline=False)
    await interaction.followup.send(embed=embed)

@tree.command(name="ac_storage", description="Read storage for a collection")
@app_commands.describe(collection="Collection name", key="Key (optional)")
async def ac_storage(interaction: discord.Interaction, collection: str, key: str = ""):
    await interaction.response.defer()
    token = get_token()
    if not token:
        await interaction.followup.send("No valid token.")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if key:
        resp = requests.get(f"{BASE_URL}/v2/storage/{collection}/{key}", headers=headers)
    else:
        resp = requests.post(f"{BASE_URL}/v2/storage", json={"collection": collection, "limit": 100}, headers=headers)

    text = json.dumps(resp.json(), indent=2)
    if len(text) > 1900:
        text = text[:1900] + "\n... (truncated)"
    await interaction.followup.send(f"```json\n{text}\n```")

# --- Run both ---
def run_bot():
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("[warn] no DISCORD_TOKEN set, bot not starting")

if __name__ == "__main__":
    load_tokens()

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
