import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_uptime() -> str:
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.readline().split()[0])
        d = int(seconds // 86400)
        h = int((seconds % 86400) // 3600)
        m = int((seconds % 3600) // 60)
        return f"{d}d {h}h {m}m"
    except Exception:
        return "unknown"


def get_memory() -> str:
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        info = {}
        for line in lines:
            parts = line.split()
            if parts[0] in ('MemTotal:', 'MemAvailable:'):
                info[parts[0]] = int(parts[1])
        total = info['MemTotal:'] / 1024
        avail = info['MemAvailable:'] / 1024
        used  = total - avail
        pct   = (used / total) * 100
        return f"{used:.0f}MB used / {total:.0f}MB total ({pct:.0f}%)"
    except Exception:
        return "unknown"


def get_disk() -> str:
    try:
        st = os.statvfs(str(Path.home()))
        total = (st.f_blocks * st.f_frsize) / (1024**3)
        free  = (st.f_bfree  * st.f_frsize) / (1024**3)
        used  = total - free
        pct   = (used / total) * 100
        return f"{used:.1f}GB used / {total:.1f}GB total ({pct:.0f}%)"
    except Exception:
        return "unknown"


def get_cpu_temp() -> str:
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            temp = int(f.read()) / 1000
        return f"{temp:.1f}°C"
    except Exception:
        return "unknown"


HELP_TEXT = """```
🏠 Archie Commands

DATABASE
  !status          — entry count + last updated
  !list            — all entries (formatted)
  !dump            — raw database as JSON
  !find <term>     — search entries for a term
  !category <cat>  — list entries by category
  !remove <id>     — delete entry by ID number
  !reset           — wipe entire database (asks to confirm)
  !reset confirm   — wipe without prompt

SYSTEM
  !sysinfo         — Pi CPU temp, RAM, disk, uptime
  !config          — show current LLM provider + model
  !provider <name> — switch provider: gemini|claude|openai|ollama
  !model <name>    — override model name
  !restart         — restart the Archie service
  !gitpull         — pull latest from GitHub + restart
  !version         — show bot version info

HELP
  !help            — this menu
```"""


async def handle_command(message, content: str, db: dict, save_db_fn, load_db_fn, env_path: Path) -> str | None:
    """
    Returns a reply string, or None if not a command.
    Handles all ! commands.
    """
    parts = content.strip().split(maxsplit=1)
    cmd   = parts[0].lower()
    args  = parts[1].strip() if len(parts) > 1 else ""

    # ── Help ──────────────────────────────────────────────────────────────────
    if cmd == "!help":
        return HELP_TEXT

    # ── Status ────────────────────────────────────────────────────────────────
    if cmd == "!status":
        entries  = db.get("entries", [])
        updated  = db.get("last_updated", "never")
        cats     = {}
        for e in entries:
            c = e.get("category", "misc")
            cats[c] = cats.get(c, 0) + 1
        cat_str = "\n".join(f"  {k}: {v}" for k, v in sorted(cats.items()))
        return f"```\n📊 Database Status\nEntries: {len(entries)}\nLast updated: {updated}\n\nBy category:\n{cat_str or '  (empty)'}\n```"

    # ── List ─────────────────────────────────────────────────────────────────
    if cmd in ("!list", "!dump"):
        entries = db.get("entries", [])
        if not entries:
            return "Database is empty."
        if cmd == "!dump":
            text = json.dumps(db, indent=2)
            if len(text) > 1800:
                text = text[:1800] + "\n... (truncated)"
            return f"```json\n{text}\n```"
        lines = []
        for e in entries:
            skip = {"id", "category", "added", "last_updated"}
            parts_list = [f"[{e['id']}] [{e.get('category','?').upper()}]"]
            for k, v in e.items():
                if k in skip:
                    continue
                if isinstance(v, list):
                    parts_list.append(f"{k}: {', '.join(str(i) for i in v)}")
                elif v:
                    parts_list.append(f"{k}: {v}")
            lines.append(" | ".join(parts_list))
        text = "\n".join(lines)
        if len(text) > 1800:
            text = text[:1800] + "\n... (truncated, use !dump for full JSON)"
        return f"```\n{text}\n```"

    # ── Find ──────────────────────────────────────────────────────────────────
    if cmd == "!find":
        if not args:
            return "Usage: `!find <search term>`"
        term    = args.lower()
        entries = db.get("entries", [])
        hits    = []
        for e in entries:
            if term in json.dumps(e).lower():
                skip = {"id", "category", "added"}
                parts_list = [f"[{e['id']}] [{e.get('category','?').upper()}]"]
                for k, v in e.items():
                    if k in skip:
                        continue
                    if isinstance(v, list):
                        parts_list.append(f"{k}: {', '.join(str(i) for i in v)}")
                    elif v:
                        parts_list.append(f"{k}: {v}")
                hits.append(" | ".join(parts_list))
        if not hits:
            return f"No entries found matching `{args}`"
        return f"```\n" + "\n".join(hits) + "\n```"

    # ── Category ──────────────────────────────────────────────────────────────
    if cmd in ("!category", "!cat"):
        if not args:
            cats = set(e.get("category","misc") for e in db.get("entries",[]))
            return f"Available categories: {', '.join(sorted(cats)) or 'none'}\nUsage: `!category appliance`"
        cat     = args.lower()
        entries = [e for e in db.get("entries",[]) if e.get("category","").lower() == cat]
        if not entries:
            return f"No entries with category `{cat}`"
        lines = []
        for e in entries:
            skip = {"id","category","added"}
            parts_list = [f"[{e['id']}]"]
            for k,v in e.items():
                if k in skip: continue
                if isinstance(v, list):
                    parts_list.append(f"{k}: {', '.join(str(i) for i in v)}")
                elif v:
                    parts_list.append(f"{k}: {v}")
            lines.append(" | ".join(parts_list))
        return f"```\n[{cat.upper()}] — {len(entries)} entries\n" + "\n".join(lines) + "\n```"

    # ── Remove ────────────────────────────────────────────────────────────────
    if cmd == "!remove":
        if not args or not args.isdigit():
            return "Usage: `!remove <id>` — use `!list` to see IDs"
        target_id = int(args)
        entries   = db.get("entries", [])
        match     = next((e for e in entries if e.get("id") == target_id), None)
        if not match:
            return f"No entry with ID {target_id}"
        entries.remove(match)
        db["entries"] = entries
        save_db_fn(db)
        name = match.get("item") or match.get("name") or "entry"
        return f"🗑️ Removed [{target_id}] {name}"

    # ── Reset ─────────────────────────────────────────────────────────────────
    if cmd == "!reset":
        if args == "confirm":
            count = len(db.get("entries", []))
            db["entries"] = []
            save_db_fn(db)
            return f"🗑️ Cleared {count} entries."
        return "⚠️ This will delete ALL entries. Type `!reset confirm` to proceed."

    # ── Sysinfo ───────────────────────────────────────────────────────────────
    if cmd == "!sysinfo":
        return f"```\n🖥️  System Info\nUptime:   {get_uptime()}\nCPU Temp: {get_cpu_temp()}\nMemory:   {get_memory()}\nDisk:     {get_disk()}\nPython:   {sys.version.split()[0]}\nPlatform: {platform.machine()}\n```"

    # ── Config ────────────────────────────────────────────────────────────────
    if cmd == "!config":
        provider = os.getenv("LLM_PROVIDER", "?")
        model    = os.getenv("LLM_MODEL", "(default)")
        db_path  = os.getenv("DB_PATH", "?")
        allowed  = os.getenv("ALLOWED_USERS", "?")
        return f"```\n⚙️  Config\nProvider: {provider}\nModel:    {model}\nDB Path:  {db_path}\nAllowed:  {allowed}\n```"

    # ── Provider switch ───────────────────────────────────────────────────────
    if cmd == "!provider":
        valid = {"gemini", "claude", "openai", "ollama"}
        if args.lower() not in valid:
            return f"Valid providers: {', '.join(sorted(valid))}"
        _update_env(env_path, "LLM_PROVIDER", args.lower())
        return f"✅ Provider set to `{args.lower()}`. Restart with `!restart` to apply."

    # ── Model override ────────────────────────────────────────────────────────
    if cmd == "!model":
        if not args:
            return "Usage: `!model <model-name>` e.g. `!model gemini-2.5-flash`"
        _update_env(env_path, "LLM_MODEL", args.strip())
        return f"✅ Model set to `{args.strip()}`. Restart with `!restart` to apply."

    # ── Restart ───────────────────────────────────────────────────────────────
    if cmd == "!restart":
        await message.reply("♻️ Restarting...")
        subprocess.Popen(["systemctl", "--user", "restart", "archie"])
        return None

    # ── Git pull ──────────────────────────────────────────────────────────────
    if cmd == "!gitpull":
        try:
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True, text=True,
                cwd=Path(__file__).parent
            )
            output = result.stdout.strip() or result.stderr.strip()
            await message.reply(f"```\n{output[:1800]}\n```")
            await message.reply("♻️ Restarting to apply changes...")
            subprocess.Popen(["systemctl", "--user", "restart", "archie"])
        except Exception as e:
            return f"❌ Git pull failed: {e}"
        return None

    # ── Version ───────────────────────────────────────────────────────────────
    if cmd == "!version":
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True, text=True,
                cwd=Path(__file__).parent
            )
            log = result.stdout.strip() or "No git history"
        except Exception:
            log = "Git not available"
        return f"```\n🏠 Archie\nPython: {sys.version.split()[0]}\n\nRecent commits:\n{log}\n```"

    return None  # Not a command


def _update_env(env_path: Path, key: str, value: str):
    """Update or add a key in the .env file."""
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    else:
        lines = []

    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n")

