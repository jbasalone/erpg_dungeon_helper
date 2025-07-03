import discord
import settings
from utils_patch import safe_send
from utils_bot import is_channel_allowed, should_handle_edit
import dungeon_helpers.dungeon11 as d11  # D11 logic lives here

def is_d11_embed_msg(message: discord.Message) -> bool:
    """
    Detects if the message is a D11 embed (works for both initial and normal board).
    """
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    embed = message.embeds[0]
    embed_dict = embed.to_dict()
    fields = embed_dict.get("fields", [])
    author = embed_dict.get("author", {}).get("name", "")
    # Allow either the 'intro' or 'normal' D11 embed structure
    if (
            len(fields) >= 2 and
            "ultra-edgy dragon" in fields[0]["name"].lower() and
            ("map" in fields[1]["name"].strip().lower() or "what will you do" in fields[1]["name"].strip().lower()) and
            " — dungeon" in author
    ):
        return True
    if embed.title and 'you have encountered **the ultra-edgy dragon**' in embed.title.lower():
        return True
    return False

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
        print(f"[D11 Edit] Failed to check edit: {exc}")
        return False

async def handle_d11_message(
        message: discord.Message,
        *,
        is_edit: bool = None,
        from_new_message: bool = None
):
    """
    Handles both new D11 messages and edits.
    """
    # Normalize to a single bool for "is this an edit"
    if is_edit is not None:
        edit = is_edit
    elif from_new_message is not None:
        edit = not from_new_message
    else:
        edit = False

    # Deduplicate only for new messages
    if not edit:
        already = getattr(settings, "ALREADY_HANDLED_MESSAGES", [])
        if message.id in already:
            return
        already.append(message.id)
        if len(already) > 5000:
            already.clear()
        settings.ALREADY_HANDLED_MESSAGES = already

    # Permission check
    if not is_channel_allowed(message.channel.id, "d11", settings):
        return

    # Delegate to core D11 logic
    try:
        await d11.handle_d11_move(
            message.embeds[0],
            message.channel,
            not edit  # True for new messages, False for edits
        )
    except Exception as exc:
        print(f"[D11] Exception in handle_d11_message: {exc}")

async def handle_d11_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    """
    Detects and dispatches raw-edit events for D11 embeds.
    Returns True if the event was handled.
    """
    if not is_d11_embed_edit(payload):
        return False

    # Skip our own edits
    author_id = int(payload.data.get("author", {}).get("id", 0))
    if author_id == settings.BOT_ID:
        return False

    # Only handle if in-flight or allowed to start on edit
    if payload.channel_id not in settings.DUNGEON11_HELPERS and not should_handle_edit(payload, "d11"):
        return False

    try:
        channel = await settings.bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        await handle_d11_message(message, is_edit=True)
        return True
    except Exception as exc:
        print(f"[D11] Exception in handle_d11_edit: {exc}")
        return False

async def warn_low_hp_if_needed(channel: discord.TextChannel, hp: int):
    """
    Send a warning if the player's HP is below 1000, before dungeon starts.
    Should be called at the dungeon command detection stage, if possible.
    """
    if hp < 1000:
        await safe_send(
            channel,
            "> ⚠️ **Warning:** Your HP is below 1000! D11 is much safer if you have 1000+ HP."
            " Consider using a healing command before entering, or you may die instantly!"
        )