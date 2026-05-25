import discord
import json
import os
import re
import aiohttp
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from abc import ABC, abstractmethod
from commands import handle_command

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH       = Path(os.getenv("DB_PATH", str(Path.home() / "home-bot" / "database.json")))
ALLOWED_USERS = [u.strip() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()]
PROVIDER      = os.getenv("LLM_PROVIDER", "gemini").lower()
ENV_PATH      = Path(__file__).parent / ".env"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_HOST    = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
MODEL_OVERRIDE = os.getenv("LLM_MODEL", "")

PROVIDER_DEFAULTS = {
    "gemini": "gemini-2.5-flash-lite-preview-06-17",
    "claude": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "ollama": OLLAMA_MODEL,
}

# ── Database ──────────────────────────────────────────────────────────────────
def load_db() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH) as f:
            return json.load(f)
    return {"entries": [], "meta": {"created": datetime.now().isoformat()}}

def save_db(db: dict):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db["last_updated"] = datetime.now().isoformat()
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)

def db_to_text(db: dict) -> str:
    if not db.get("entries"):
        return "(empty — nothing stored yet)"
    lines = []
    for e in db["entries"]:
        parts = [f"[{e.get('category','misc').upper()}]"]
        for k, v in e.items():
            if k in {"id", "category", "added"}:
                continue
            if isinstance(v, list):
                parts.append(f"{k}: {', '.join(str(i) for i in v)}")
            elif v:
                parts.append(f"{k}: {v}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM = """You are Archie, a home and family knowledge base assistant.

Your ONLY jobs are storing facts and answering questions about them.

RULE 1 — STORING:
If the message contains ANY fact about the home or family, store it immediately.
This includes: appliances, model numbers, filter sizes, people, preferences, gift ideas,
paint colors, room info, vehicles, pets, warranties — anything factual about the household.
Phrases like "my X is Y", "we have a Z", "my wife likes X", "the filter is 16x25x1" are ALL facts.
Do NOT give advice. Do NOT ask clarifying questions. Just confirm and store.
After storing, mention any interesting connections to existing entries.

RULE 2 — ANSWERING:
Scan EVERY SINGLE entry in the database before answering. Do NOT stop at the first match.
List ALL matching entries — never omit any.
"What appliances do I have?" = list EVERY entry with category=appliance.
"What LG stuff?" = list EVERY entry where brand=LG.
"What's in the laundry room?" = list EVERY entry where location=laundry room.
"Gift ideas for my wife?" = pull her likes, dislikes, and gift ideas.
If there are 5 matching entries, return all 5.

RULE 3 — CASUAL: respond naturally. No store block needed.

Current database:
--- START ---
{database}
--- END ---

When storing, end your reply with this block using EXACT delimiters:
<<STORE>>
{{"category":"appliance","item":"washing machine","brand":"LG","model":"WM4000","location":"laundry room","tags":["laundry room"]}}
<<ENDSTORE>>

Categories: appliance | person | preference | filter | vehicle | pet | room | maintenance | gift | misc

Person example:
<<STORE>>
{{"category":"person","name":"Sarah","relationship":"wife","likes":["tulips"],"dislikes":["carnations"],"gift_ideas":["cookbook"],"tags":["family"]}}
<<ENDSTORE>>

Only include relevant fields. Always use double quotes. Keep reply to 2-3 sentences before the store block."""

# ── LLM Providers ─────────────────────────────────────────────────────────────
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        pass

class GeminiProvider(LLMProvider):
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.model   = MODEL_OVERRIDE or PROVIDER_DEFAULTS["gemini"]

    async def complete(self, system: str, user: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as r:
                raw = await r.text()
                print(f"[Gemini]: {raw[:300]}")
                data = json.loads(raw)
                return data["candidates"][0]["content"]["parts"][0]["text"]

class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.api_key = CLAUDE_API_KEY
        self.model   = MODEL_OVERRIDE or PROVIDER_DEFAULTS["claude"]

    async def complete(self, system: str, user: str) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": user}]
        }
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
                raw = await r.text()
                print(f"[Claude]: {raw[:300]}")
                data = json.loads(raw)
                return data["content"][0]["text"]

class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.model   = MODEL_OVERRIDE or PROVIDER_DEFAULTS["openai"]

    async def complete(self, system: str, user: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user}
            ]
        }
        async with aiohttp.ClientSession() as s:
            async with s.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as r:
                raw = await r.text()
                print(f"[OpenAI]: {raw[:300]}")
                data = json.loads(raw)
                return data["choices"][0]["message"]["content"]

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.host  = OLLAMA_HOST
        self.model = MODEL_OVERRIDE or PROVIDER_DEFAULTS["ollama"]

    async def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user}
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 8192}
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{self.host}/api/chat", json=payload, timeout=aiohttp.ClientTimeout(total=180)) as r:
                raw = await r.text()
                print(f"[Ollama]: {raw[:300]}")
                data = json.loads(raw)
                return data["message"]["content"]

def get_provider() -> LLMProvider:
    providers = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }
    if PROVIDER not in providers:
        raise ValueError(f"Unknown LLM_PROVIDER '{PROVIDER}'. Choose: {list(providers.keys())}")
    return providers[PROVIDER]()

# ── Store block parsing ───────────────────────────────────────────────────────
def extract_store(response: str) -> dict | None:
    match = re.search(r"<<STORE>>\s*(\{.*?\})\s*<<ENDSTORE>>", response, re.DOTALL)
    if not match:
        return None
    try:
        cleaned = match.group(1).replace("{{", "{").replace("}}", "}")
        raw = json.loads(cleaned)
        return {k: v for k, v in raw.items() if v not in (None, "", [], {})}
    except Exception as e:
        print(f"⚠️  Store parse error: {e}")
        return None

def clean_response(response: str) -> str:
    return re.sub(r"<<STORE>>.*?<<ENDSTORE>>", "", response, flags=re.DOTALL).strip()

# ── Discord ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
client  = discord.Client(intents=intents)
llm     = get_provider()

@client.event
async def on_ready():
    db = load_db()
    print(f"✅ Archie online as {client.user}")
    print(f"   Provider: {PROVIDER} | Model: {MODEL_OVERRIDE or PROVIDER_DEFAULTS.get(PROVIDER,'?')} | Entries: {len(db['entries'])}")

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if ALLOWED_USERS:
        if str(message.author.id) not in ALLOWED_USERS and str(message.author.name) not in ALLOWED_USERS:
            return

    content = message.content.strip()
    print(f"\n📨 {message.author}: {content}")

    # ── Command handling ──────────────────────────────────────────────────────
    if content.startswith("!"):
        db    = load_db()
        reply = await handle_command(message, content, db, save_db, load_db, ENV_PATH)
        if reply:
            for i in range(0, len(reply), 1900):
                await message.reply(reply[i:i+1900])
        return

    # ── LLM handling ──────────────────────────────────────────────────────────
    async with message.channel.typing():
        db     = load_db()
        count  = len(db.get("entries", []))
        hint   = f"[There are {count} total entries in the database. When listing, return ALL matches.]\n\n"
        system = SYSTEM.format(database=db_to_text(db))

        try:
            response = await llm.complete(system, hint + content)
        except Exception as e:
            print(f"❌ LLM error: {e}")
            await message.reply(f"❌ LLM error: {e}")
            return

        print(f"💬 {response[:300]}")

        store_data = extract_store(response)
        if store_data:
            store_data["id"]    = len(db["entries"]) + 1
            store_data["added"] = datetime.now().isoformat()
            db["entries"].append(store_data)
            save_db(db)
            print(f"✅ Stored #{store_data['id']}: {store_data.get('item') or store_data.get('name','?')}")

        reply = clean_response(response) or "✅ Stored."
        for i in range(0, len(reply), 1900):
            await message.reply(reply[i:i+1900])

client.run(DISCORD_TOKEN)

