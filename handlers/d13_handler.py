import discord
import random
import settings
import dung_helpers
from utils_bot import is_channel_allowed, should_handle_edit, find_last_bot_answer_message, is_slash_dungeon

def is_d13_embed_msg(message: discord.Message) -> bool:
    if not message.embeds:
        return False
    embed = message.embeds[0]
    # D13 is unique: always has a field with both "room:" and "ultra-omega dragon"
    for field in embed.fields:
        val = (field.value or "").lower()
        if "room:" in val and "ultra-omega dragon" in val:
            print("[D13 DETECT DEBUG] Matched on field value:", val)
            return True
    return False

def is_d13_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    try:
        embeds = payload.data.get("embeds", [])
        if not embeds:
            return False
        # Simulate embed.fields parsing
        for field in embeds[0].get("fields", []):
            val = (field.get("value") or "").lower()
            if "room:" in val and "ultra-omega dragon" in val:
                print("[D13 DETECT EDIT DEBUG] Matched on field value:", val)
                return True
        print("[D13 DETECT EDIT DEBUG] No D13 match")
        return False
    except Exception as e:
        print("[D13 DETECT EDIT EXCEPTION]", e)
        return False


async def handle_d13_message(
        message: discord.Message,
        from_new_message: bool,
        bot_answer_message: discord.Message = None,
):
    print(f"[D13] handle_d13_message called: from_new_message={from_new_message}, message_id={message.id}, channel_id={message.channel.id}")

    # Channel check
    if not is_channel_allowed(message.channel.id, "d13", settings):
        print("[D13] Channel not allowed.")
        return

    embed = message.embeds[0]

    # Reset state on new dungeon start
    if embed.title and embed.title.startswith("YOU HAVE ENCOUNTERED THE ULTRA-OMEGA DRAGON"):
        settings.DUNGEON13_HELPERS.pop(message.channel.id, None)

    # Determine slash vs. message dungeon
    message_based = not is_slash_dungeon(message)  # True for classic rpg dungeon, False for slash

    # For slash dungeons, bot_answer_message must be passed for in-place editing.
    # For message-based, always send a new message, never edit!
    answer_msg = await dung_helpers.d13_helper(
        embed, message.channel,
        from_message=from_new_message,
        bot_answer_message=bot_answer_message if not message_based else None,  # Only use for slash
        trigger_message=message,
        helpers=settings.DUNGEON13_HELPERS,
        message_based=message_based
    )

    # Save reference for later edits (slash dungeon support)
    if hasattr(settings, "DUNGEON13_LAST_ANSWER_MSG") and answer_msg:
        settings.DUNGEON13_LAST_ANSWER_MSG[message.channel.id] = answer_msg

async def handle_d13_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    if not is_d13_embed_edit(payload):
        return False
    if int(payload.data.get("author", {}).get("id", 0)) == settings.BOT_ID:
        return False
    if payload.channel_id not in settings.DUNGEON13_HELPERS and not should_handle_edit(payload, "d13"):
        return False


    try:
        channel = await settings.bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        bot_answer_message = getattr(settings, "DUNGEON13_LAST_ANSWER_MSG", {}).get(channel.id, None)
        if not bot_answer_message:
            bot_answer_message = await find_last_bot_answer_message(
                channel, settings.BOT_ID, after_message_id=message.id
            )

        await handle_d13_message(message, from_new_message=False, bot_answer_message=bot_answer_message)
        return True
    except Exception as e:
        print(f"[D13 ERROR] Exception in handle_d13_edit: {e}")
        return False