import re
import discord
import inspect
from typing import Union
from utils_patch import safe_send
import settings
import bot_commands
import sqlitedict

from handlers import (
    d10_handler, d11_handler, d12_handler, d13_handler,
    d14_handler, d15_handler, d15_2_handler, slash_handler
)

bot = settings.bot

# Keep track of which channels & dungeon-tags are in "slash mode"
# so that their first board-embed edits the same helper message.
# For simplicity, we only need slash-mode for d15; other dungeons treat is_edit.
settings.DUNGEON15_LAST_WAS_SLASH = set()

# Each entry: (tag, embed_detector, handler)
DUNGEON_HANDLERS = [
    (10,   d10_handler.is_d10_embed_msg,    d10_handler.handle_d10_message),
    (11,   d11_handler.is_d11_embed_msg,    d11_handler.handle_d11_message),
    (12,   d12_handler.is_d12_embed_msg,    d12_handler.handle_d12_message),
    (13,   d13_handler.is_d13_embed_msg,    d13_handler.handle_d13_message),
    (14,   d14_handler.is_d14_embed_msg,    d14_handler.handle_d14_message),
    (15,   d15_handler.is_d15_embed_msg,    d15_handler.handle_d15_message),
    (15.2, d15_2_handler.is_d15_2_embed_msg, d15_2_handler.handle_d15_2_message),
]
TAG_TO_HANDLER = {str(tag): handler for tag, _, handler in DUNGEON_HANDLERS}

# Raw-edit dispatcher for all dungeons
EDIT_HANDLERS = [
    d10_handler.handle_d10_edit,
    d11_handler.handle_d11_edit,
    d12_handler.handle_d12_edit,
    d13_handler.handle_d13_edit,
    d14_handler.handle_d14_edit,
    d15_handler.handle_d15_edit,
    d15_2_handler.handle_d15_2_edit,
]

def should_send_new_message(event_type: str, message: discord.Message, channel_id: int) -> bool:
    """
    Determines if the bot should send a new message (legacy) or edit its existing answer (slash).
    Returns True if legacy (send), False if slash (edit).
    """
    # Edits are always slash dungeons
    if event_type == "edit":
        return False

    # If discord.py 2.x and message has interaction, it's a slash command
    if hasattr(message, "interaction") and message.interaction is not None:
        return False

    # If using a tracker for channels with an active slash dungeon, check that too:
    if hasattr(settings, "LAST_SLASH_DUNGEON_CALL") and channel_id in settings.LAST_SLASH_DUNGEON_CALL:
        return False

    # Fallback: assume all new messages from Epic RPG bot are legacy unless tracked as slash
    return True

def is_channel_allowed(channel_id, tag):
    channel_id_str = str(channel_id)
    # Always use 'd12', 'd13', ... for all keys!
    tag_str = f'd{str(tag).replace("d", "").replace(".2", ".2")}'
    key = f"{channel_id_str}{tag_str.lower()}"
    #print(f"[is_channel_allowed] Lookup: '{key}' in allowed_channels: {key in settings.allowed_channels}")
    return settings.ALLOW_HELPERS_IN_ALL_CHANNELS or key in settings.allowed_channels

async def note_dungeon_confirmation(channel: discord.TextChannel, tag: Union[int, float]):
    # Only send one notice per entry
    if channel.id in settings.NOTED_MESSAGE:
        return
    if not is_channel_allowed(channel.id, tag):
        return
    msg = await safe_send(channel, f"> 📘 Noted: Dungeon `{tag}` confirmed. Awaiting board…")
    settings.NOTED_MESSAGE[channel.id] = msg

async def detect_confirmation_buttons(payload) -> bool:
    # Catch the "Are you sure you want to enter..." button payload
    author = int(payload.data.get("author", {}).get("id", 0))
    if author != settings.EPIC_RPG_ID:
        return False
    # skip if already mid-run
    if any(payload.channel_id in m for m in settings.DUNGEON_HELPERS_MAP.values()):
        return False

    embeds  = payload.data.get("embeds") or []
    content = (payload.data.get("content") or "").lower()
    # Plain-text confirmation
    if not embeds and "are you sure you want to enter" in content:
        m = re.search(r'dungeon\s+`?(\d{1,2}(?:\.2)?)`?', content)
    else:
        # Embed-based confirmation
        comp = payload.data.get("components") or []
        if not embeds or comp and comp[0]["components"][0].get("disabled"):
            return False
        title = (embeds[0].get("title") or "").lower()
        if "are you sure you want to enter" not in title:
            return False
        authn = embeds[0].get("author", {}).get("name", "")
        m     = re.search(r'dungeon\s+`?(\d{1,2}(?:\.2)?)`?', authn, re.IGNORECASE)
    if not m:
        return False

    tag = float(m.group(1)) if '.' in m.group(1) else int(m.group(1))
    settings.LAST_SLASH_DUNGEON_CALL[payload.channel_id] = tag
    chan = await bot.fetch_channel(payload.channel_id)
    await note_dungeon_confirmation(chan, tag)
    return True


async def dispatch_fallback(message: discord.Message, tag: Union[int, float, str]):
    settings.DUNGEON15_LAST_WAS_SLASH.add(message.channel.id)
    tag_str = str(tag)
    handler = TAG_TO_HANDLER.get(tag_str)

    if handler and is_channel_allowed(message.channel.id, tag_str):
        await handler(message, from_new_message=False)  # <- FIXED HERE

async def dispatch_dungeon_embed(message: discord.Message, event_type: str) -> bool:
    cid = message.channel.id
    for tag, is_fn, handle_fn in DUNGEON_HANDLERS:
        if is_fn(message):
            if not is_channel_allowed(cid, tag):
                return False
            from_new_message = should_send_new_message(event_type, message, cid)
            print(f"Calling {handle_fn.__name__} with from_new_message={from_new_message}")
            await handle_fn(message, from_new_message=from_new_message)
            return True
    return False

@bot.event
async def on_message(message: discord.Message):
    """
    Main message event.
    - Responds to GH commands (view/help/add/remove) from any user/channel FIRST.
    - Only proceeds to dungeon processing for Epic RPG bot messages in allowed channels.
    """

    # 1) GH-prefix commands: view / help / add / remove (any user/channel)
    text = message.content.strip()
    cmd = None
    if text.lower().startswith(settings.PREFIX + " "):
        cmd = text[len(settings.PREFIX)+1:].strip()
    elif text.lower() == settings.PREFIX:
        cmd = ""
    if cmd is not None:
        if cmd.startswith("view"):
            await bot_commands.view_available_helpers_in_channel(
                message.channel, message.author, cmd)
            return
        if cmd.startswith(("help", "add", "remove")):
            # Permission: allowed roles or dev or Epic
            if message.author.id not in (settings.DEV_USER_ID, settings.EPIC_RPG_ID):
                has_role = any(
                    discord.utils.get(message.guild.roles, id=r) in message.author.roles
                    for r in settings.ALLOWED_ROLES_TO_USE_COMMANDS
                )
                if not has_role:
                    return
            if cmd.startswith("help"):
                await bot_commands.help_command(message.channel, message.author)
            elif cmd.startswith("add"):
                await bot_commands.add_helper_to_channel(
                    message.channel, message.author, cmd)
            else:
                await bot_commands.remove_helper_from_channel(
                    message.channel, message.author, cmd)
            return

    # 2) Only process Epic RPG bot messages for dungeon helpers
    if message.author.id != settings.EPIC_RPG_ID:
        return

    # 3) Only process allowed channels unless global allowed
    if not settings.ALLOW_HELPERS_IN_ALL_CHANNELS and not any(
            is_channel_allowed(message.channel.id, tag) for tag, _, _ in DUNGEON_HANDLERS
    ):
        # Uncomment for debugging:
        #print(f"Skipped message in channel {message.channel.id}: Not allowed for any dungeon tag")
        return

    # 4) Slash dungeon text command handler (custom handler)
    if slash_handler.is_dungeon_text_command(message):
        settings.LAST_SLASH_DUNGEON_CALL.pop(message.channel.id, None)
        settings.DUNGEON15_LAST_WAS_SLASH.discard(message.channel.id)
        await slash_handler.handle_dungeon_text_command(message)
        return

    # 5) Slash: "Entering the EPIC dungeon..." first embed
    if message.channel.id in settings.LAST_SLASH_DUNGEON_CALL and message.embeds:
        tag = settings.LAST_SLASH_DUNGEON_CALL.pop(message.channel.id)
        await dispatch_fallback(message, tag)
        return

    # 6) Any dungeon embed: let dispatch decide (and handler decides send/edit)
    if message.embeds and await dispatch_dungeon_embed(message, event_type="message"):
        return

    # 7) Fallback: pass message to process_commands
    await bot.process_commands(message)


@bot.event
async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):
    """
    Responds to message edits (embed updates) from the Epic RPG bot
    Only in allowed channels for the dungeons being handled.
    """
    author_id = int(payload.data.get("author", {}).get("id", 0))
    if author_id != settings.EPIC_RPG_ID:
        return

    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        return

    # Only process allowed channels unless global allowed
    if not settings.ALLOW_HELPERS_IN_ALL_CHANNELS and not any(
            is_channel_allowed(payload.channel_id, tag) for tag, _, _ in DUNGEON_HANDLERS
    ):
        return

    try:
        edited_message = await channel.fetch_message(payload.message_id)
    except Exception:
        return

    # Debug: Uncomment if you want to see when edits are received
    print(f"[EVENT] on_raw_message_edit: edited message: {edited_message}, channel: {channel}")

    if edited_message.embeds and await dispatch_dungeon_embed(edited_message, event_type="edit"):
        return

if __name__ == "__main__":
    bot.run(settings.BOT_TOKEN)
