# utils_bot.py

import settings
import discord

def is_channel_allowed(channel_id: int, dungeon_tag: str, settings) -> bool:
    key = f"{channel_id}{dungeon_tag}"
    if settings.ALLOW_HELPERS_IN_ALL_CHANNELS or key in settings.allowed_channels:
        print(f"[CHANNEL CHECK] {key} allowed: True")
        return True

    # 🔁 Allow during active sessions
    active = (
            dungeon_tag == "d10" and channel_id in settings.DUNGEON10_HELPERS or
            dungeon_tag == "d11" and channel_id in settings.DUNGEON11_HELPERS or
            dungeon_tag == "d12" and channel_id in settings.DUNGEON12_HELPERS or
            dungeon_tag == "d13" and channel_id in settings.DUNGEON13_HELPERS or
            dungeon_tag == "d14" and channel_id in settings.DUNGEON14_HELPERS or
            dungeon_tag == "d15" and channel_id in settings.DUNGEON15_HELPERS or
            dungeon_tag == "d15.2" and channel_id in settings.DUNGEON15_2_HELPERS
    )

    print(f"[CHANNEL CHECK] {key} allowed: {active} (via active session)")
    return active

def should_handle_edit(payload: discord.RawMessageUpdateEvent, dungeon_tag: str) -> bool:
    try:
        message_id = int(payload.data['id'])
        if message_id in settings.ALREADY_HANDLED_MESSAGES:
            return False

        settings.ALREADY_HANDLED_MESSAGES.append(message_id)
        if len(settings.ALREADY_HANDLED_MESSAGES) > 5000:
            settings.ALREADY_HANDLED_MESSAGES.clear()

        key = f"{payload.channel_id}{dungeon_tag}"
        allowed = settings.ALLOW_HELPERS_IN_ALL_CHANNELS or key in settings.allowed_channels

        active_session = (
                dungeon_tag == "d10" and payload.channel_id in settings.DUNGEON10_HELPERS
                or dungeon_tag == "d11" and payload.channel_id in settings.DUNGEON11_HELPERS
                or dungeon_tag == "d12" and payload.channel_id in settings.DUNGEON12_HELPERS
                or dungeon_tag == "d13" and payload.channel_id in settings.DUNGEON13_HELPERS
                or dungeon_tag == "d14" and payload.channel_id in settings.DUNGEON14_HELPERS
                or dungeon_tag == "d15" and payload.channel_id in settings.DUNGEON15_HELPERS
                or dungeon_tag == "d15.2" and payload.channel_id in settings.DUNGEON15_2_HELPERS
        )

        # ✅ Key addition — allow if we previously noted the dungeon tag
        slash_detected = payload.channel_id in settings.LAST_SLASH_DUNGEON_CALL

        if not allowed and not active_session and not slash_detected:
            return False

        return True
    except (KeyError, ValueError, TypeError):
        return False

def is_dungeon_edit(payload_data: dict) -> bool:
    try:
        embed = payload_data['embeds'][0]
        bot_author_id = int(payload_data['author']['id'])

        if bot_author_id != settings.EPIC_RPG_ID:
            return False

        # Check "author" field for " — dungeon" pattern (covers D10–D14, D15.2)
        author_name = embed.get("author", {}).get("name", "")
        if " — dungeon" in author_name:
            return True

        # Fallback: Check for known D15 title pattern
        title = embed.get("title", "") or ""
        if "TIME DRAGON" in title.upper():
            return True

        return False
    except (IndexError, KeyError, TypeError):
        return False

async def find_last_bot_answer_message(channel: discord.TextChannel, bot_id: int, after_message_id: int = None):
    """
    Scans the last 20 messages in the channel (or thread) to find the most recent message from the bot.
    Optionally, skip any message with the same ID as after_message_id.
    Returns the message object or None.
    """
    async for m in channel.history(limit=20, oldest_first=False):
        if m.author.id == bot_id and (after_message_id is None or m.id != after_message_id):
            return m
    return None

# utils_bot.py or top of dung_helpers.py
def is_slash_dungeon(message) -> bool:
    """
    Returns True if the dungeon is a slash-command dungeon (edit previous bot answers),
    False if classic/message-based dungeon (always send new message).
    Works with discord.Message, edit payload dict, or RawMessageUpdateEvent.
    """
    # Discord.py 2.x+ (slash command message): has .interaction
    if hasattr(message, "interaction") and message.interaction is not None:
        return True
    # Author is bot, name ends with "— dungeon", and message is not classic 'rpg dungeon'
    try:
        author = getattr(message, "author", None)
        content = getattr(message, "content", None)
        if author and getattr(author, "bot", False):
            name = getattr(author, "name", "")
            if name and name.lower().endswith("— dungeon"):
                if not content or not content.lower().startswith("rpg "):
                    return True
    except Exception:
        pass
    # For dict or payload-like objects (for edit events)
    try:
        author = message.get("author", {})
        name = author.get("name", "")
        if name.lower().endswith("— dungeon"):
            content = message.get("content", None)
            if not content or not content.lower().startswith("rpg "):
                return True
    except Exception:
        pass
    return False

async def d14_send(channel, content, state, from_message):
    """
    Helper for sending or editing D14 bot answers.
    """
    if not from_message and getattr(state, "message", None):
        try:
            await state.message.edit(content=content)
            return state.message
        except Exception:
            pass
    return await channel.send(content)