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

async def handle_d11_message(
        message: discord.Message,
        *,
        is_edit: bool = None,
        from_new_message: bool = None
):
    # Deduplicate by message ID
    if (not hasattr(settings, "D11_HANDLED_MESSAGE_IDS")
            or not isinstance(settings.D11_HANDLED_MESSAGE_IDS, set)):
        print("[WARN] D11_HANDLED_MESSAGE_IDS was missing or not a set. Resetting to set()!")
        settings.D11_HANDLED_MESSAGE_IDS = set()
    if message.id in settings.D11_HANDLED_MESSAGE_IDS:
        print(f"[D11] Already handled Discord message id {message.id}")
        return
    settings.D11_HANDLED_MESSAGE_IDS.add(message.id)
    if len(settings.D11_HANDLED_MESSAGE_IDS) > 1000:
        settings.D11_HANDLED_MESSAGE_IDS.clear()

    if not is_channel_allowed(message.channel.id, "d11", settings):
        return

    try:
        await d11.handle_d11_move(
            message.embeds[0],
            message.channel,
            True  # LEGACY: always send a new message per move
        )
    except Exception as exc:
        print(f"[D11] Exception in handle_d11_message: {exc}")

# (Edits are never used in legacy! But leave this for API symmetry)
async def handle_d11_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    return False