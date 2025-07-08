import discord
import settings
from utils_patch import safe_send
from utils_bot import is_channel_allowed, should_handle_edit
import dungeon_helpers.dungeon11 as d11
from utils_cache import get_message_with_cache


def is_d11_embed_msg(message: discord.Message) -> bool:
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    embed = message.embeds[0]
    embed_dict = embed.to_dict()
    fields = embed_dict.get("fields", [])
    author = embed_dict.get("author", {}).get("name", "")
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
    edit = is_edit if is_edit is not None else not from_new_message if from_new_message is not None else False

    # Only deduplicate new messages
    if not edit:
        already = getattr(settings, "ALREADY_HANDLED_MESSAGES", [])
        if message.id in already:
            return
        already.append(message.id)
        if len(already) > 5000:
            already.clear()
        settings.ALREADY_HANDLED_MESSAGES = already

    if not is_channel_allowed(message.channel.id, "d11", settings):
        return

    try:
        await d11.handle_d11_move(
            message.embeds[0],
            message.channel,
            not edit  # True for new messages, False for edits
        )
    except Exception as exc:
        print(f"[D11] Exception in handle_d11_message: {exc}")

async def handle_d11_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    if not is_d11_embed_edit(payload):
        return False
    author_id = int(payload.data.get("author", {}).get("id", 0))
    if author_id == settings.BOT_ID:
        return False
    if payload.channel_id not in settings.DUNGEON11_HELPERS and not should_handle_edit(payload, "d11"):
        return False
    try:
        channel = await settings.bot.fetch_channel(payload.channel_id)
        message = await get_message_with_cache(channel, payload.message_id)
        await handle_d11_message(message, is_edit=True)
        return True
    except Exception as exc:
        print(f"[D11] Exception in handle_d11_edit: {exc}")
        return False