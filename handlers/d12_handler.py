import discord
import settings
import dungeon_helpers.dungeon12 as dung12
import time
from utils_bot import should_handle_edit, find_last_bot_answer_message

def is_d12_embed_msg(message: discord.Message) -> bool:
    if message.author.id not in (settings.EPIC_RPG_ID, settings.UTILITY_NECROBOT_ID, settings.BETA_BOT_ID):
        return False
    if not message.embeds:
        return False
    embed = message.embeds[0]
    return dung12.is_d12_embed(message.author.id, embed)

def is_d12_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    embeds = payload.data.get("embeds", [])
    author_id = int(payload.data.get("author", {}).get("id", 0))
    if author_id != settings.EPIC_RPG_ID or not embeds:
        return False
    try:
        embed = discord.Embed.from_dict(embeds[0])
        if hasattr(dung12, "is_d12_embed") and dung12.is_d12_embed(author_id, embed):
            return True
        d = embeds[0]
        title = d.get('title', '').lower()
        author = d.get('author', {}).get('name', '').lower()
        if 'omega dragon' in title or 'omega dragon' in author:
            return True
    except Exception:
        pass
    return False

async def handle_d12_message(message: discord.Message, from_new_message: bool):
    # DEDUPLICATION - put this at the very top, before any logic
    if not hasattr(settings, "ALREADY_HANDLED_D12_MSGS"):
        settings.ALREADY_HANDLED_D12_MSGS = set()
    msg_key = (message.channel.id, message.id)
    if msg_key in settings.ALREADY_HANDLED_D12_MSGS:
        print(f"[D12] SKIP already handled: {msg_key}")
        return
    settings.ALREADY_HANDLED_D12_MSGS.add(msg_key)
    if len(settings.ALREADY_HANDLED_D12_MSGS) > 10000:
        settings.ALREADY_HANDLED_D12_MSGS.clear()

    print(f"[D12] HANDLING: {msg_key}, from_new_message={from_new_message}")

    # Get last bot answer if needed
    answer_message = None
    if not from_new_message:
        if hasattr(settings, "DUNGEON12_LAST_ANSWER_MSG"):
            answer_message = settings.DUNGEON12_LAST_ANSWER_MSG.get(message.channel.id)
        # If not found, try to find it in channel
        if answer_message is None:
            answer_message = await find_last_bot_answer_message(
                message.channel, settings.BOT_ID, after_message_id=message.id
            )
    # Call the actual D12 logic
    new_answer = await dung12.handle_dungeon_12(
        embed=message.embeds[0],
        channel=message.channel,
        from_new_message=from_new_message,
        bot_answer_message=answer_message,
        message=message
    )
    if hasattr(settings, "DUNGEON12_LAST_ANSWER_MSG") and new_answer is not None:
        settings.DUNGEON12_LAST_ANSWER_MSG[message.channel.id] = new_answer

async def handle_d12_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    if not is_d12_embed_edit(payload):
        return False
    if int(payload.data.get("author", {}).get("id", 0)) == settings.BOT_ID:
        return False
    if not should_handle_edit(payload, "d12"):
        return False

    # DEDUPE/THROTTLE
    key = (payload.channel_id, payload.message_id)
    now = time.time()
    last_time = getattr(settings, "D12_EDIT_RECENT", {}).get(key, 0)
    if now - last_time < 1.5:
        return False
    if not hasattr(settings, "D12_EDIT_RECENT"):
        settings.D12_EDIT_RECENT = {}
    settings.D12_EDIT_RECENT[key] = now
    if len(settings.D12_EDIT_RECENT) > 10000:
        settings.D12_EDIT_RECENT.clear()

    # Use only payload data!
    try:
        channel = await settings.bot.fetch_channel(payload.channel_id)
        embeds = payload.data.get("embeds", [])
        if not embeds:
            return False
        embed = discord.Embed.from_dict(embeds[0])
        await dung12.handle_dungeon_12(
            embed=embed,
            channel=channel,
            from_new_message=False,
            bot_answer_message=None,
            message=None  # <-- No full message fetched!
        )
        return True
    except Exception as exc:
        print(f"[D12] Error in handle_d12_edit: {exc}")
        return False