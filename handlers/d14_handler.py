import asyncio
import discord
import dung_helpers
import settings
import time
from typing import Optional, Tuple, Dict


from dung_helpers import (
    is_d14_embed,
    get_d14_map_data,
    solve_d14_c,
    MOVE_EMOJI,
)
from utils_bot import is_channel_allowed

VICTORY_SENT = set()
LAST_BOT_MSG = {}
LAST_D14_HANDLED = {} # channel_id: (msg_id, when)
DEBOUNCE_SECONDS = 2
LAST_D14_PLAN: Dict[int, Tuple[list, list, int, float, int, int, int]] = {}
#         (solution, tiles_path, hp_req, elapsed, step, Y, X)
def save_plan(key: int, plan):
    LAST_D14_PLAN[key] = plan

def load_plan(key: int):
    return LAST_D14_PLAN.get(key)

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

async def handle_d14_message(message: discord.Message, from_new_message: bool = None):
    # 0. Preconditions
    if not is_channel_allowed(message.channel.id, "d14", settings) or not message.embeds:
        return

    channel = message.channel
    embed = message.embeds[0].to_dict()
    is_slash = is_slash_dungeon(message)

    # 1. Debounce rapid-fire edits
    now = time.monotonic()
    prev = LAST_D14_HANDLED.get(channel.id)
    if prev and prev[0] == message.id and now - prev[1] < DEBOUNCE_SECONDS:
        return
    LAST_D14_HANDLED[channel.id] = (message.id, now)

    # 2. Victory check
    victory_key = (channel.id, message.id)
    if is_d14_victory_embed(embed):
        if victory_key not in VICTORY_SENT:
            VICTORY_SENT.add(victory_key)
            last_bot = LAST_BOT_MSG.pop(channel.id, None)
            LAST_D14_PLAN.pop(channel.id, None)
            LAST_D14_HANDLED.pop(channel.id, None)
            if last_bot:
                await safe_edit(last_bot, content="> <:ep_greenleaf:1375735418292801567> **CONGRATULATIONS** 🎉")
            else:
                await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> **CONGRATULATIONS** 🎉")
        return

    # 3. Pre-move: recommend first step
    if is_d14_embed(embed) == 2:
        try:
            MAP, HP, Y, X = get_d14_map_data(embed, None, None)
            tile, move = dung_helpers.get_best_d14_start_move(MAP, X, Y)
            name = dung_helpers.D14ids_TILES_DICT.get(tile, "Unknown").capitalize()
            desc_map = {
                dung_helpers.D14ids.BROWN.value: "🟫 Brown",
                dung_helpers.D14ids.GREEN.value: "🟩 Green",
                dung_helpers.D14ids.YELLOW.value: "🟨 Yellow",
                dung_helpers.D14ids.ORANGE.value: "🟧 Orange",
                dung_helpers.D14ids.BLUE.value: "🟦 Blue",
                dung_helpers.D14ids.PURPLE.value: "🟪 Purple",
                dung_helpers.D14ids.RED.value: "🟥 Red",
            }
            tile_desc = desc_map.get(tile, "⬜ Unknown")
            move_desc = {"UP":"⬆️ Up","DOWN":"⬇️ Down","LEFT":"⬅️ Left","RIGHT":"➡️ Right"}.get(move, move.capitalize())

            await safe_send(
                channel,
                f"""\
<:ep_greenleaf:1375735418292801567> **RECOMMENDED STARTING MOVE**

‣ **Move:** {move_desc}
‣ **To Tile:** {tile_desc}

🕹️ _Move onto a {name} tile to maximize solver success!_
⚡ *Tip: The solver only calculates after your first move!*"""
            )
        except Exception as exc:
            print(f"[D14 START ERROR] {exc}")
            await safe_send(channel, f"> Unable to suggest a starting move. ({exc})")
        return

    # 4. Post-move: parse state
    try:
        MAP, HP, Y, X = get_d14_map_data(embed, None, None)
    except Exception as e:
        print(f"[D14] Map parse error: {e}")
        return

    # if dragon gone, clean up and exit
    if not any(8 in row for row in MAP):
        LAST_BOT_MSG.pop(channel.id, None)
        LAST_D14_PLAN.pop(channel.id, None)
        return

    # 5. Load or compute plan
    plan = load_plan(channel.id)
    should_resolve = True
    step = 0

    if plan:
        solution, tiles_path, hp_req, elapsed, prev_step, prev_Y, prev_X = plan
        print(f"[D14 PLAN] step={prev_step}, pos={(Y,X)}, prev={(prev_Y,prev_X)}")

        if prev_step < len(solution):
            next_move = solution[prev_step]
            expected_pos = tiles_path[prev_step]
            # ATTACK/PASS TURN: must stay on same tile
            if next_move in ("ATTACK", "PASS TURN") and (Y, X) == (prev_Y, prev_X):
                step = prev_step + 1
                should_resolve = False
                print(f"  > Player executed {next_move} at tile {expected_pos} (no movement) -> step {step}")
            # NORMAL move: must have moved to expected tile
            elif (Y, X) == expected_pos:
                step = prev_step + 1
                should_resolve = False
                print(f"  > Player moved to expected next tile in plan, step {step}")
            # JUMPED ahead: furthest matching tile forward (never back)
            elif (Y, X) in tiles_path[prev_step+1:]:
                idx = max(i for i, pos in enumerate(tiles_path[prev_step+1:], start=prev_step+1) if pos == (Y, X))
                step = idx + 1
                should_resolve = False
                print(f"  > Player jumped ahead to tile {tiles_path[idx]}, jumping to step {step}")
            else:
                should_resolve = True
                print(f"  > Move not found in plan, replanning")
                if is_slash:
                    last_msg = LAST_BOT_MSG.get(channel.id)
                    if last_msg:
                        await safe_edit(last_msg, content="> ⚠️ Detected an unexpected move. <:ep_greenleaf:1375735418292801567> Recomputing the solution…")
                    else:
                        await safe_send(channel, "> ⚠️ Detected an unexpected move. <:ep_greenleaf:1375735418292801567> Recomputing the solution…")
            if not should_resolve:
                save_plan(channel.id, (solution, tiles_path, hp_req, elapsed, step, Y, X))

    if should_resolve:
        # 6. “Solving...” status
        if is_slash:
            last_msg = LAST_BOT_MSG.get(channel.id)
            if last_msg:
                try:
                    await safe_edit(last_msg, content="> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")
                except:
                    last_msg = await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")
                    LAST_BOT_MSG[channel.id] = last_msg
            else:
                last_msg = await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")
                LAST_BOT_MSG[channel.id] = last_msg
            msg = last_msg
        else:
            msg = await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> 🕒 **Solving...**")

        # 7. Compute new path
        solution, tiles, attempts, hp_req, elapsed = await solve_d14_c(
            MAP, Y, X, HP,
            yellow_poison=0,
            orange_poison=0,
            inital_message=msg
        )
        tiles_path = path_from_moves(Y, X, solution)
        step = 0
        save_plan(channel.id, (solution, tiles_path, hp_req, elapsed, step, Y, X))
    else:
        solution, tiles_path, hp_req, elapsed = plan[0:4]

    # 8. Output next move
    if not solution or step >= len(solution):
        if is_slash:
            last_msg = LAST_BOT_MSG.get(channel.id)
            if last_msg:
                await safe_edit(last_msg, content="> <:ep_greenleaf:1375735418292801567> All moves complete, waiting for victory!")
            else:
                await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> All moves complete, waiting for victory!")
        else:
            await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> All moves complete, waiting for victory!")
        return

    move = solution[step]
    tile_yx = tiles_path[step]
    turns_left = len(solution) - (step + 1)
    emoji = MOVE_EMOJI.get(move, "❓")
    color_val = MAP[tile_yx[0]][tile_yx[1]]
    color_name = dung_helpers.D14ids_TILES_DICT.get(color_val, str(color_val)).capitalize()
    out = f"> **{emoji} {move}** to {color_name} {tile_yx} [{turns_left} turns left]\n"

    if is_slash:
        last_msg = LAST_BOT_MSG.get(channel.id)
        try:
            await safe_edit(last_msg, content=out)
        except:
            msg = await safe_send(channel, out)
            LAST_BOT_MSG[channel.id] = msg
    else:
        await safe_send(channel, out)
# --- helpers (unchanged) ---

def path_from_moves(start_y, start_x, moves):
    y, x = start_y, start_x
    path = []
    for move in moves:
        if move == "UP":
            y -= 1
        elif move == "DOWN":
            y += 1
        elif move == "LEFT":
            x -= 1
        elif move == "RIGHT":
            x += 1
        # skip ATTACK and PASS TURN as they don't move player
        path.append((y, x))
    return path

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