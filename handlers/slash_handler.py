# handlers/slash_handler.py

import re
import discord
import settings
from utils_patch import safe_send

def is_dungeon_text_command(message: discord.Message) -> bool:
    """Detects a legacy 'dungeon 13', 'dungeon 15.2', etc text command from EPIC RPG."""
    if message.author.id != settings.EPIC_RPG_ID:
        return False
    return bool(re.search(r'dungeon\s+`?\d{1,2}(\.2)?`?', (message.content or "").lower()))

async def handle_dungeon_text_command(message: discord.Message):
    """Handles a text-based dungeon command and sets slash-mode marker."""
    m = re.search(r'dungeon\s+`?(\d{1,2}(\.2)?)`?', (message.content or "").lower())
    if not m:
        return
    tag = m.group(1)
    try:
        tag_num = float(tag) if '.' in tag else int(tag)
        settings.LAST_SLASH_DUNGEON_CALL[message.channel.id] = tag_num
        await safe_send(message.channel, f"> 📘 Noted: Dungeon `{tag}` detected. I’ll assist once it starts!")
    except Exception:
        pass  # ignore bad matches

def is_dungeon_slash_message(message: discord.Message) -> bool:
    """Detects a slash-based dungeon message (embed with Start/Enter button from EPIC RPG)."""
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    embed = message.embeds[0].to_dict()
    author = embed.get("author", {})
    if " — dungeon" not in author.get("name", ""):
        return False
    # Looks for a button labeled 'Start' or 'Enter'
    try:
        for row in getattr(message, "components", []):
            for component in getattr(row, "children", []):
                if getattr(component, "label", "").lower() in ("start", "enter"):
                    return True
    except Exception:
        pass
    return False

async def handle_dungeon_slash_message(message: discord.Message):
    """Handles a slash-based dungeon message and sets slash-mode marker."""
    embed = message.embeds[0].to_dict()
    author_name = embed.get("author", {}).get("name", "")
    m = re.search(r'Dungeon\s+(\d{1,2}(?:\.\d)?)', author_name, re.IGNORECASE)
    tag_str = m.group(1) if m else "15"
    tag_num = float(tag_str) if "." in tag_str else int(tag_str)
    settings.LAST_SLASH_DUNGEON_CALL[message.channel.id] = tag_num
    await safe_send(
        message.channel,
        f"> ✅ `/dungeon {tag_str}` command detected. I’ll assist once it begins!"
    )