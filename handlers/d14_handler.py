import asyncio
import random
import copy
import discord
import dung_helpers
import settings
import re

from dung_helpers import (
    is_d14_embed,
    get_d14_map_data,
    get_best_d14_start_move,
    solve_d14_c,
    MOVE_EMOJI,
    D14ids_TILES_DICT,
    RANDOM_EMOJIS,
    D14ids,
    apply_d14_move,
)
from settings import DUNGEON14_HELPERS
from utils_bot import is_channel_allowed

LAST_PROCESSED_STEP = {}
LAST_MOVE_SENT = {}
VICTORY_SENT = set()

def do_move(board, y, x, move):
    if move == "UP":
        return y-1, x
    if move == "DOWN":
        return y+1, x
    if move == "LEFT":
        return y, x-1
    if move == "RIGHT":
        return y, x+1
    return y, x  # ATTACK or PASS TURN, stay in place

def get_board_key(MAP, HP, Y, X):
    return "|".join([
        "".join(str(x) for row in MAP for x in row),
        str(HP),
        f"{Y},{X}"
    ])

def is_d14_embed_msg(message: discord.Message) -> bool:
    if not message.embeds:
        return False
    return is_d14_embed(message.embeds[0].to_dict()) != 0

def is_d14_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    embeds = payload.data.get("embeds", [])
    if not embeds:
        return False
    return dung_helpers.is_d14_embed(embeds[0]) != 0

def dragon_still_on_map(MAP):
    for row in MAP:
        if 8 in row:
            return True
    return False

def simulate_position(orig_map, orig_y, orig_x, orig_hp, moves, idx):
    y, x, hp = orig_y, orig_x, orig_hp
    sim_map = copy.deepcopy(orig_map)
    for move in moves[:idx]:
        y, x, hp = apply_d14_move(sim_map, y, x, hp, move)
    return y, x, hp

async def handle_d14_message(message, from_new_message):
    if not is_channel_allowed(message.channel.id, "d14", settings) or not message.embeds:
        return

    channel = message.channel
    embed = message.embeds[0].to_dict()

    # --- VICTORY CASE ---
    victory_key = (channel.id, message.id)
    if is_d14_victory_embed(embed):
        if victory_key in VICTORY_SENT:
            return
        VICTORY_SENT.add(victory_key)
        print(f"[D14 DEBUG] Detected dungeon completion in embed. Sending congratulations!")
        await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> **CONGRATULATIONS** You have cleared Dungeon 14!")
        DUNGEON14_HELPERS.pop(channel.id, None)
        for k in list(LAST_PROCESSED_STEP.keys()):
            if k[0] == channel.id:
                LAST_PROCESSED_STEP.pop(k, None)
        for k in list(LAST_MOVE_SENT.keys()):
            if k[0] == channel.id:
                LAST_MOVE_SENT.pop(k, None)
        return

    dungeon_type = is_d14_embed(embed)  # 0=not D14, 1=post-move, 2=initial

    try:
        MAP, HP, Y, X = get_d14_map_data(embed, None, None)
        board_key = get_board_key(MAP, HP, Y, X)
    except Exception as e:
        print(f"[D14 DEBUG] Map parse error: {e}")
        return

    state = DUNGEON14_HELPERS.get(channel.id)

    # --- INITIAL ENCOUNTER: Greedy move only ---
    if dungeon_type == 2:
        print(f"[D14 DEBUG] INITIAL ENCOUNTER. State: {state}")
        DUNGEON14_HELPERS.pop(channel.id, None)
        try:
            tile, move = get_best_d14_start_move(MAP, X, Y)
            print(f"[D14 DEBUG] Sending greedy move: {move} to {tile}")
            bot_msg = await safe_send(channel, f"> **{MOVE_EMOJI[move]} {move}** to {D14ids_TILES_DICT.get(tile, tile)}")
            DUNGEON14_HELPERS[channel.id] = ["initial", tile, move, bot_msg, random.randint(1, 1_000_000_000)]
        except Exception as e:
            print(f"[D14 DEBUG] Map parse error: {e}")
        return

    # --- ACTIVE STEPPER: Solution in progress ---
    def board_states_match(map1, map2):
        for r1, r2 in zip(map1, map2):
            if r1 != r2:
                return False
        return True

    if state and isinstance(state, list) and len(state) >= 10 and state[0] == "solved":
        # Robust unpacking for legacy/updated state
        state_fields = state[1:]
        # pad with None as needed (up to 11 fields for backwards compatibility)
        while len(state_fields) < 11:
            state_fields.append(None)
        soln, idx, bot_msg, soln_tiles, _, anchor_map, anchor_y, anchor_x, anchor_hp, old_board_key, state_id = state_fields[:11]

        if not dragon_still_on_map(MAP):
            print(f"[D14 DEBUG] Dragon is gone from the map. Invalidating old solution and rerunning solver.")
            DUNGEON14_HELPERS.pop(channel.id, None)
        else:
            found = False
            matched_idx = None
            for next_idx in range(len(soln) + 1):
                sim_map = copy.deepcopy(anchor_map)
                y_sim, x_sim, hp_sim = anchor_y, anchor_x, anchor_hp
                for move in soln[:next_idx]:
                    y_sim, x_sim, hp_sim = apply_d14_move(sim_map, y_sim, x_sim, hp_sim, move)
                if (Y, X) == (y_sim, x_sim) and HP == hp_sim and board_states_match(MAP, sim_map):
                    matched_idx = next_idx
                    found = True
                    break
            if found:
                idx = matched_idx
                DUNGEON14_HELPERS[channel.id][2] = idx
                key = (channel.id, idx, message.id)
                if LAST_PROCESSED_STEP.get(key):
                    print(f"[D14 DEBUG] RETURN: Already processed this step: {key}")
                    return
                LAST_PROCESSED_STEP[key] = True

                if idx >= len(soln):
                    await asyncio.sleep(2)
                    await safe_edit(bot_msg, content=f"> <:ep_greenleaf:1375735418292801567> **CONGRATULATIONS** {random.choice(RANDOM_EMOJIS)}")
                    DUNGEON14_HELPERS.pop(channel.id, None)
                    for k in list(LAST_PROCESSED_STEP.keys()):
                        if k[0] == channel.id:
                            LAST_PROCESSED_STEP.pop(k, None)
                    return

                next_move = soln[idx]
                next_tile = soln_tiles[idx]
                turns_left = len(soln) - idx - 1
                key_simple = (channel.id, idx)
                if from_new_message and LAST_MOVE_SENT.get(key_simple) == next_move:
                    print(f"[D14 DEBUG] Skipping duplicate move after user input: {next_move} at idx={idx}")
                    return
                # Only send/edit if state_id is still valid!
                if len(DUNGEON14_HELPERS.get(channel.id, [])) > 10 and DUNGEON14_HELPERS.get(channel.id, [None]*11)[10] != state_id:
                    print("[D14 DEBUG] Skipping stale stepper due to state_id mismatch.")
                    return
                if from_new_message:
                    await safe_send(
                        channel,
                        f"> **{MOVE_EMOJI[next_move]} {next_move}** to {next_tile} [{turns_left} turns left]"
                    )
                else:
                    await safe_edit(
                        bot_msg,
                        content=f"> **{MOVE_EMOJI[next_move]} {next_move}** to {next_tile} [{turns_left} turns left]"
                    )
                    DUNGEON14_HELPERS[channel.id][3] = bot_msg

                LAST_MOVE_SENT[key_simple] = next_move
                print(f"[D14 DEBUG] After move: idx={DUNGEON14_HELPERS[channel.id][2]} / {len(soln)}")
                prev_key = (channel.id, idx-1, message.id)
                LAST_PROCESSED_STEP.pop(prev_key, None)
                return
            else:
                print(f"[D14 DEBUG] Board out of sync: actual=({Y},{X}), HP={HP}, not on solution path. Rerunning solver.")
                DUNGEON14_HELPERS.pop(channel.id, None)  # FULLY clear state
    # --- LAUNCH SOLVER if not in-search or solution not present ---
    state = DUNGEON14_HELPERS.get(channel.id)
    if state and state[0] == "in_search" and (len(state) < 6 or state[5] == board_key):
        print("[D14 DEBUG] Already searching this board, skipping.")
        return

    print(f"[D14 DEBUG] No active solution for this board. Launching solver.")
    state_id = random.randint(1, 1_000_000_000)
    DUNGEON14_HELPERS[channel.id] = ["in_search", None, None, None, None, board_key, state_id]
    wait_msg = await safe_send(channel, "> <:ep_greenleaf:1375735418292801567> 🕒 **Searching for a solution...**")

    # --- The solver must be launched here and MUST use local variables ---
    async def run_solver(local_state_id):
        soln, soln_tiles, attempts, hp_req, elapsed = await solve_d14_c(
            MAP, Y, X, HP, yellow_poison=0, orange_poison=0, inital_message=wait_msg
        )
        print(f"[D14 DEBUG] Solver returned: soln={soln} hp_req={hp_req} elapsed={elapsed}")
        if DUNGEON14_HELPERS.get(channel.id, [None]*7)[6] != local_state_id:
            print("[D14 DEBUG] Skipping run_solver stale state_id.")
            return
        if not soln:
            await safe_edit(wait_msg, content="> <:ep_greenleaf:1375735418292801567> **This dungeon is impossible** with your current HP.")
            DUNGEON14_HELPERS.pop(channel.id, None)
            return

        # Align idx to current position (full board, pos, and HP match)
        idx = 0
        for step in range(len(soln)):
            sim_map = copy.deepcopy(MAP)
            y_sim, x_sim, hp_sim = Y, X, HP
            for m in soln[:step+1]:
                y_sim, x_sim, hp_sim = apply_d14_move(sim_map, y_sim, x_sim, hp_sim, m)
            if (y_sim, x_sim) == (Y, X) and hp_sim == HP and board_states_match(MAP, sim_map):
                idx = step + 1

        # Save new solution with state_id
        DUNGEON14_HELPERS[channel.id] = [
            "solved", soln, idx, wait_msg, soln_tiles, board_key,
            MAP, Y, X, HP, local_state_id
        ]

        if idx < len(soln):
            next_move = soln[idx]
            next_tile = soln_tiles[idx]
            turns_left = len(soln) - idx - 1
            await safe_edit(
                wait_msg,
                content=(
                    f"> <:ep_greenleaf:1375735418292801567> Solution found:\n"
                    f"> ♥ **HP REQUIRED:** ~{hp_req}\n"
                    f"> ⏳ **FOUND IN:** {elapsed}s • 🆒 **ATTEMPTS:** {attempts}\n\n"
                    f"> ➡️ **{MOVE_EMOJI[next_move]} {next_move}** to {next_tile} [{turns_left} turns left]"
                )
            )
        else:
            await safe_edit(wait_msg, content=f"> **CONGRATULATIONS** {random.choice(RANDOM_EMOJIS)}")
            DUNGEON14_HELPERS.pop(channel.id, None)
        print(f"[D14 DEBUG] State set to SOLVED: {DUNGEON14_HELPERS[channel.id]}")

    asyncio.create_task(run_solver(state_id))  # <--- This launches the solver

    print(f"[D14 DEBUG] MAIN RETURN (no action) at end. cid={channel.id} type={dungeon_type} new={from_new_message} state={state} msgid={message.id}")

async def safe_send(channel, *args, **kwargs):
    try:
        return await channel.send(*args, **kwargs)
    except discord.errors.HTTPException as exc:
        if exc.status == 429:
            retry_after = getattr(exc, "retry_after", 2)
            await asyncio.sleep(retry_after)
            return await channel.send(*args, **kwargs)
        raise

async def safe_edit(message, *args, **kwargs):
    try:
        return await message.edit(*args, **kwargs)
    except discord.errors.HTTPException as exc:
        if exc.status == 429:
            retry_after = getattr(exc, "retry_after", 2)
            await asyncio.sleep(retry_after)
            return await message.edit(*args, **kwargs)
        raise

async def handle_d14_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    if not is_d14_embed_edit(payload):
        return False
    embeds = payload.data.get("embeds", [])
    if not embeds or dung_helpers.is_d14_embed(embeds[0]) == 2:
        return False
    author = int(payload.data.get("author",{}).get("id",0))
    if author == settings.BOT_ID:
        return False
    if payload.channel_id not in DUNGEON14_HELPERS:
        return False
    channel = await settings.bot.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    await handle_d14_message(message, from_new_message=False)
    return True

def is_d14_victory_embed(embed: dict) -> bool:
    # Only consider as victory if the field matches the *EXACT* HP string, or exact kill string
    for field in embed.get("fields", []):
        name = field.get("name", "").lower()
        value = field.get("value", "").replace(',', '').lower().strip()
        # Victory by kill string
        if "godly dragon" in name:
            if "has killed the godly dragon" in value:
                print("[D14 Victory Test] Matched kill string in value:", value)
                return True
            # Victory by exact HP line - must be a line **THE GODLY DRAGON** — :purple_heart: 0/2000 (or similar)
            for line in value.splitlines():
                m = re.match(r"\*\*the godly dragon\*\* — :purple_heart: ?0/2000$", line.strip())
                if m:
                    print("[D14 Victory Test] Matched HP zero line:", line.strip())
                    return True

    if "footer" in embed and embed["footer"].get("text"):
        footer = embed["footer"]["text"].lower().strip()
        if "has unlocked the next area" in footer or "unlocked commands:" in footer:
            print("[D14 Victory Test] Matched footer victory:", footer)
            return True
    return False