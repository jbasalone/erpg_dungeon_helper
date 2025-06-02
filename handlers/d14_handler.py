import asyncio
import discord
import dung_helpers
import settings
import re
import hashlib
import time

from dung_helpers import (
    is_d14_embed,
    get_d14_map_data,
    solve_d14_c,
    MOVE_EMOJI,
)
from utils_bot import is_channel_allowed

VICTORY_SENT = set()
LAST_BOT_MSG = {}
LAST_D14_PLAN = {}    # channel_id: (state_hash, solution, tiles, hp_req, elapsed, step_idx)
LAST_D14_HANDLED = {} # channel_id: (msg_id, when)
DEBOUNCE_SECONDS = 2

def is_slash_dungeon(message):
    t = getattr(message, "type", None)
    return getattr(t, "value", t) == 20

def is_d14_embed_msg(message: discord.Message) -> bool:
    if not message.embeds:
        return False
    return is_d14_embed(message.embeds[0].to_dict()) != 0

def is_d14_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    embeds = payload.data.get("embeds", [])
    if not embeds:
        return False
    return dung_helpers.is_d14_embed(embeds[0]) != 0

def map_state_hash(MAP, HP, Y, X):
    s = str(MAP) + f"|{HP}|{Y}|{X}"
    return hashlib.sha1(s.encode()).hexdigest()

async def handle_d14_message(message, from_new_message=None):
    if not is_channel_allowed(message.channel.id, "d14", settings) or not message.embeds:
        return

    channel = message.channel
    embed = message.embeds[0].to_dict()
    is_slash = is_slash_dungeon(message)

    key = (message.channel.id, message.id)
    now = time.monotonic()
    prev = LAST_D14_HANDLED.get(message.channel.id)
    if prev and prev[0] == message.id and now - prev[1] < DEBOUNCE_SECONDS:
        return  # Ignore duplicate events for this message in the debounce window
    LAST_D14_HANDLED[message.channel.id] = (message.id, now)

    # ----- 1. Victory check -----
    victory_key = (channel.id, message.id)
    if is_d14_victory_embed(embed):
        if victory_key not in VICTORY_SENT:
            VICTORY_SENT.add(victory_key)
            # Cleanup all state after win
            LAST_D14_PLAN.pop(channel.id, None)
            LAST_D14_HANDLED.pop(channel.id, None)
            LAST_BOT_MSG.pop(channel.id, None)
            if is_slash:
                last_bot_msg = LAST_BOT_MSG.pop(channel.id, None)
                if last_bot_msg:
                    try:
                        await safe_edit(last_bot_msg, content="> <:ep_greenleaf:1375735418292801567> **CONGRATULATIONS** 🎉")
                    except Exception:
                        pass
                else:
                    await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> **CONGRATULATIONS** 🎉")
            else:
                await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> **CONGRATULATIONS** 🎉")
        return

    # ----- 2. Parse map, hp, player y/x from the embed -----
    try:
        MAP, HP, Y, X = get_d14_map_data(embed, None, None)
    except Exception as e:
        print(f"[D14] Map parse error: {e}")
        return

    state_hash = map_state_hash(MAP, HP, Y, X)

    # 3. If dragon is not on the map, clean up for slash & exit
    if not any(8 in row for row in MAP):
        LAST_BOT_MSG.pop(channel.id, None)
        LAST_D14_PLAN.pop(channel.id, None)
        return

    # 4. Check for an existing plan
    plan = LAST_D14_PLAN.get(channel.id)
    should_resolve = True
    step = 0

    if plan:
        cached_hash, solution, tiles, hp_req, elapsed, prev_step = plan

        # Only accept plan if the current state matches the next expected step
        # Advance the step if user is following the plan
        if cached_hash == state_hash and solution and prev_step < len(solution):
            # User didn't move, or event spam, just repeat advice
            step = prev_step
            should_resolve = False
        elif (
                solution and prev_step + 1 < len(solution)
                and map_state_hash(MAP, HP, Y, X) == map_state_hash(MAP, HP, Y, X)
        ):
            # Shouldn't really ever match here, just a placeholder for extensibility
            step = prev_step + 1
            should_resolve = False
        elif solution and prev_step < len(solution) - 1:
            # Try to see if the user followed the last suggestion:
            # Move from (prev Y/X) to expected tile
            last_tile = tiles[prev_step]
            # If user's current (Y,X) == last_tile, advance step
            if (Y, X) == last_tile:
                step = prev_step + 1
                should_resolve = False
            else:
                # User deviated! Re-solve from here
                should_resolve = True
        else:
            should_resolve = True

    if should_resolve:
        # Re-solve from the current position, reset to step 0
        msg = None
        if is_slash:
            last_bot_msg = LAST_BOT_MSG.get(channel.id)
            if last_bot_msg is None:
                msg = await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")
                LAST_BOT_MSG[channel.id] = msg
            else:
                try:
                    msg = await safe_edit(last_bot_msg, content="> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")
                    LAST_BOT_MSG[channel.id] = msg
                except (discord.NotFound, AttributeError):
                    msg = await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")
                    LAST_BOT_MSG[channel.id] = msg
        else:
            msg = await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")
        solution, tiles, attempts, hp_req, elapsed = await solve_d14_c(
            MAP, Y, X, HP, yellow_poison=0, orange_poison=0, inital_message=msg
        )
        if not solution or not tiles or len(solution) != len(tiles):
            warn = f"[D14] Solution mismatch: len(solution)={len(solution)}, len(tiles)={len(tiles)}"
            print(warn)
            print(f"[D14 DEBUG] MAP={MAP} HP={HP} Y={Y} X={X}")
            # Cache failed state so we don't keep retrying
            LAST_D14_PLAN[channel.id] = (state_hash, None, None, None, None, 0)
            if is_slash:
                await safe_edit(msg, content="> ❌ Solution parse error. Please try again or report this.")
            else:
                await safe_send(channel, "> ❌ Solution parse error. Please try again or report this.")
            return
        # Cache solution and set step to 0
        step = 0
        LAST_D14_PLAN[channel.id] = (state_hash, solution, tiles, hp_req, elapsed, step)
    else:
        # Use cached plan, at correct step
        solution = plan[1]
        tiles = plan[2]
        hp_req = plan[3]
        elapsed = plan[4]

    # Output the next move in the plan (if not at end)
    if not solution or step >= len(solution):
        # Solution exhausted or error
        if is_slash:
            msg = LAST_BOT_MSG.get(channel.id)
            if msg:
                await safe_edit(msg, content="> 🟩 All moves complete, waiting for victory!")
            else:
                await safe_send(channel, "> 🟩 All moves complete, waiting for victory!")
        else:
            await safe_send(channel, "> 🟩 All moves complete, waiting for victory!")
        return

    next_move = solution[step]
    next_tile = tiles[step]
    turns_left = len(solution) - (step + 1)
    out_str = (
        f"> **{MOVE_EMOJI[next_move]} {next_move}** to {next_tile} [{turns_left} turns left]\n"
        f"> *(HP Required: {hp_req} | Found in: {elapsed}s)*"
    )

    if is_slash:
        msg = LAST_BOT_MSG.get(channel.id)
        if msg:
            try:
                await safe_edit(msg, content=out_str)
            except Exception:
                msg = await safe_send(channel, out_str)
                LAST_BOT_MSG[channel.id] = msg
        else:
            msg = await safe_send(channel, out_str)
            LAST_BOT_MSG[channel.id] = msg
    else:
        await safe_send(channel, out_str)

    # Update current step in cache
    plan = LAST_D14_PLAN[channel.id]
    LAST_D14_PLAN[channel.id] = (plan[0], plan[1], plan[2], plan[3], plan[4], step)

# --- helpers (unchanged) ---
async def safe_send(channel, *args, **kwargs):
    try:
        return await channel.send(*args, **kwargs)
    except Exception:
        await asyncio.sleep(2)
        try:
            return await channel.send(*args, **kwargs)
        except Exception as e:
            print(f"[D14] Failed to send message in {channel}: {e}")
            return None

async def safe_edit(message, *args, **kwargs):
    try:
        return await message.edit(*args, **kwargs)
    except Exception:
        await asyncio.sleep(2)
        try:
            return await message.edit(*args, **kwargs)
        except Exception as e:
            chan_id = getattr(message.channel, "id", None)
            print(f"[D14] Failed to edit bot message in {chan_id}: {e}")
            if chan_id and chan_id in LAST_BOT_MSG:
                LAST_BOT_MSG.pop(chan_id, None)
            return None

async def handle_d14_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    if not is_d14_embed_edit(payload):
        return False
    embeds = payload.data.get("embeds", [])
    if not embeds or dung_helpers.is_d14_embed(embeds[0]) == 2:
        return False
    author = int(payload.data.get("author",{}).get("id",0))
    if author == settings.BOT_ID:
        return False
    channel = await settings.bot.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    await handle_d14_message(message)
    return True

def is_d14_victory_embed(embed: dict) -> bool:
    for field in embed.get("fields", []):
        name = field.get("name", "").lower()
        value = field.get("value", "").replace(",", "").lower().strip()
        if "godly dragon" in name:
            if "has killed the godly dragon" in value:
                return True
            for line in value.splitlines():
                m = re.match(r"\*\*the godly dragon\*\* — :purple_heart: ?0/2000$", line.strip())
                if m:
                    return True
    if "footer" in embed and embed["footer"].get("text"):
        footer = embed["footer"]["text"].lower().strip()
        if "has unlocked the next area" in footer or "unlocked commands:" in footer:
            return True
    return False