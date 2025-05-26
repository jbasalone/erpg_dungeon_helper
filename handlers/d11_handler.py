# handlers/d11_handler.py

import discord
import settings
from utils_patch import safe_send
from utils_bot import is_channel_allowed, should_handle_edit
import dungeon_helpers.dungeon11 as d11  # D11 logic lives here
from typing import Any

def is_d11_embed_msg(message: discord.Message) -> bool:
    """
    Returns True if the given message is a new D11 embed from EPIC RPG.
    """
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    return d11.is_d11_embed(message.embeds[0], message.author.id)

def is_d11_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    """
    Returns True if the raw update event is an edit of a D11 embed.
    """
    try:
        author_id = int(payload.data.get("author", {}).get("id", 0))
        embeds = payload.data.get("embeds", [])
        if author_id != settings.EPIC_RPG_ID or not embeds:
            return False
        embed = discord.Embed.from_dict(embeds[0])
        return d11.is_d11_embed(embed, author_id)
    except Exception as exc:
        # Optionally log: logger.warning(f"[D11 Edit] Failed to check edit: {exc}")
        return False

async def handle_d11_message(message: discord.Message, *, is_edit: bool = False):
    """
    Handles both new D11 embeds and edits to them.
    """
    # 1) Deduplicate only for new messages
    if not is_edit:
        already = getattr(settings, "ALREADY_HANDLED_MESSAGES", [])
        if message.id in already:
            return
        already.append(message.id)
        if len(already) > 5000:
            already.clear()
        settings.ALREADY_HANDLED_MESSAGES = already

    # 2) Permission check
    if not is_channel_allowed(message.channel.id, "d11", settings):
        return

    # 3) Delegate to core D11 logic
    try:
        await d11.handle_d11_move(
            message.embeds[0],
            message.channel,
            from_message=not is_edit
        )
    except Exception as exc:
        # Optionally log: logger.error(f"[D11] Exception in handle_d11_message: {exc}")
        pass

async def handle_d11_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    """
    Detects and dispatches raw-edit events for D11 embeds.
    Returns True if the event was handled.
    """
    # 1) Pattern match
    if not is_d11_embed_edit(payload):
        return False

    # 2) Skip our own edits
    author_id = int(payload.data.get("author", {}).get("id", 0))
    if author_id == settings.BOT_ID:
        return False

    # 3) Permission logic: only handle if in-flight or allowed to start on edit
    if payload.channel_id not in settings.DUNGEON11_HELPERS \
            and not should_handle_edit(payload, "d11"):
        return False

    # 4) Re-fetch & delegate
    try:
        channel = await settings.bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        await handle_d11_message(message, is_edit=True)
        return True
    except Exception as exc:
        # Optionally log: logger.error(f"[D11] Exception in handle_d11_edit: {exc}")
        return False