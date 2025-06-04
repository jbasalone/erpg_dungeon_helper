import asyncio
import discord
import dung_helpers
import settings
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
    import hashlib
    return hashlib.sha1(s.encode()).hexdigest()

async def handle_d14_message(message, from_new_message=None):
    """
    Main handler for D14 messages. Handles:
    - Starting move recommendation (pre-move)
    - Solver step-by-step suggestions (post-move)
    - Victory handling and plan caching
    """
    if not is_channel_allowed(message.channel.id, "d14", settings) or not message.embeds:
        return

    channel = message.channel
    embed = message.embeds[0].to_dict()
    is_slash = is_slash_dungeon(message)

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

    # ----- 2. Pre-move D14: Suggest starting move -----
    if is_d14_embed(embed) == 2:
        try:
            MAP, HP, Y, X = get_d14_map_data(embed, None, None)
            tile, move = dung_helpers.get_best_d14_start_move(MAP, X, Y)
            tile_name = dung_helpers.D14ids_TILES_DICT.get(tile, "Unknown").capitalize()
            tile_emojis = {
                dung_helpers.D14ids.BROWN.value: "🟫 Brown",
                dung_helpers.D14ids.GREEN.value: "🟩 Green",
                dung_helpers.D14ids.YELLOW.value: "🟨 Yellow",
                dung_helpers.D14ids.ORANGE.value: "🟧 Orange",
                dung_helpers.D14ids.BLUE.value: "🟦 Blue",
                dung_helpers.D14ids.PURPLE.value: "🟪 Purple",
                dung_helpers.D14ids.RED.value: "🟥 Red",
            }
            tile_desc = tile_emojis.get(tile, "⬜ Unknown")

            move_emojis = {
                "UP": "⬆️ Up",
                "DOWN": "⬇️ Down",
                "LEFT": "⬅️ Left",
                "RIGHT": "➡️ Right",
            }
            move_desc = move_emojis.get(move, move.capitalize())

            await safe_send(
                channel,
                f"""\
<:ep_greenleaf:1375735418292801567> **RECOMMENDED STARTING MOVE**

‣ **Move:** {move_desc}
‣ **To Tile:** {tile_desc}

🕹️ _Move onto a {tile_name} tile to maximize solver success!_
⚡ *Tip: The solver only calculates after your first move!*"""
            )
        except Exception as exc:
            print(f"[D14 START ERROR] {exc}")
            await safe_send(channel, f"> Unable to suggest a starting move. ({exc})")
        return  # Prevent double-processing

    # ----- 3. Parse map, hp, player y/x from the embed (post-move only) -----
    try:
        MAP, HP, Y, X = get_d14_map_data(embed, None, None)
    except Exception as e:
        print(f"[D14] Map parse error: {e}")
        return

    state_hash = map_state_hash(MAP, HP, Y, X)

    # If dragon is not on the map, clean up for slash & exit
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
        if cached_hash == state_hash and solution and prev_step < len(solution):
            step = prev_step
            should_resolve = False
        elif (
                solution and prev_step + 1 < len(solution)
                and map_state_hash(MAP, HP, Y, X) == map_state_hash(MAP, HP, Y, X)
        ):
            step = prev_step + 1
            should_resolve = False
        elif solution and tiles and prev_step < len(solution) - 1 and prev_step < len(tiles):
            last_tile = tiles[prev_step]
            if (Y, X) == last_tile:
                step = prev_step + 1
                should_resolve = False
            else:
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
            LAST_D14_PLAN[channel.id] = (state_hash, None, None, None, None, 0)
            if is_slash:
                await safe_edit(msg, content="> ❌ Solution parse error. Please move to another tile or report this.")
            else:
                await safe_send(channel, "> ❌ Solution parse error. Please move to another tile or report this.")
            return
        step = 0
        LAST_D14_PLAN[channel.id] = (state_hash, solution, tiles, hp_req, elapsed, step)
    else:
        solution = plan[1]
        tiles = plan[2]
        hp_req = plan[3]
        elapsed = plan[4]

    # Output the next move in the plan (if not at end)
    if not solution or step >= len(solution):
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
    next_tile = tiles[step] if step < len(tiles) else "?"
    turns_left = len(solution) - (step + 1)
    emoji = MOVE_EMOJI.get(next_move, "❓")
    out_str = (
        f"> **{emoji} {next_move}** to {next_tile} [{turns_left} turns left]\n"
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
    import re
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