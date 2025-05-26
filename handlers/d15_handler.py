import time
import random
import discord

from utils_patch import safe_send
from utils_bot import is_channel_allowed, find_last_bot_answer_message, is_slash_dungeon
import settings
from dung_helpers import (
    RANDOM_EMOJIS,
    solve_d15_c,
    verify_d15_solution,
    D15Data,
    get_board_name_in_db,
    process_board,
    is_d15_embed as raw_is_d15,
)

# --- Helper Functions ---

def is_d15_embed_msg(message: discord.Message) -> bool:
    """
    Checks if a message is a D15 dungeon embed from Epic RPG or Beta Bot.
    """
    if not message.embeds:
        return False
    return (
            message.author.id in (settings.EPIC_RPG_ID, settings.BETA_BOT_ID)
            and raw_is_d15(message.author.id, message.embeds[0].to_dict())
    )

def is_d15_embed_edit(payload) -> bool:
    """
    Checks if an edited message (payload) is a D15 dungeon embed.
    """
    embeds = payload.data.get("embeds", [])
    if not embeds:
        return False
    author_id = int(payload.data.get("author", {}).get("id", 0))
    return raw_is_d15(author_id, embeds[0])

# --- Main Handler for New Messages or Edits ---

async def handle_d15_message(
        message: discord.Message,
        from_new_message: bool,
        bot_answer_message: discord.Message = None,
):
    """
    Handles a D15 dungeon embed message, solving and guiding the user through the solution.
    """
    if not message.embeds:
        return

    cid = message.channel.id
    channel = message.channel

    # Detect if this is a slash-mode session
    slash_mode = is_slash_dungeon(message)

    # Parse board and HP from embed
    e = message.embeds[0].to_dict()
    fields = e.get("fields", [])
    author = (e.get("author") or {}).get("name", "")
    if "— dungeon" in author and len(fields) >= 2:
        raw_hp = fields[0]["value"]
        board_txt = fields[1]["value"]
        cur_hp = int(raw_hp.split(":yellow_heart:")[1].split("/")[0].replace(",", ""))
    else:
        board_txt = fields[0]["value"]
        fallback = settings.DUNGEON15_HELPERS.get(cid)
        cur_hp = fallback.last_hp if fallback else 200

    # Debounce unchanged edits
    LAST = getattr(settings, "LAST_D15_BOARD", {})
    if not from_new_message and LAST.get(cid) == board_txt:
        return
    LAST[cid] = board_txt
    settings.LAST_D15_BOARD = LAST

    # Timeout or victory detection
    if e.get("description", "").startswith("Ok so you took too much time"):
        settings.DUNGEON15_HELPERS.pop(cid, None)
        settings.ALREADY_HANDLED_MESSAGES.clear()
        return

    # Deduplicate new messages
    if from_new_message:
        seen = getattr(settings, "ALREADY_HANDLED_MESSAGES", [])
        if message.id in seen:
            return
        seen.append(message.id)
        if len(seen) > 5000:
            seen.clear()
        settings.ALREADY_HANDLED_MESSAGES = seen

    # Permission check
    if not is_channel_allowed(cid, "d15", settings):
        return

    # --- MID-RUN: Existing session ---
    if cid in settings.DUNGEON15_HELPERS:
        data = settings.DUNGEON15_HELPERS[cid]
        expected = data.solution[0].lower()
        log_txt = e["fields"][0]["value"].lower()

        # Board changed unexpectedly, recalculate solution
        if expected != "attack" and expected not in log_txt:
            sol, _ = await solve_d15_c(board_txt, cur_hp)
            sol.append("attack")
            data.solution, data.last_board, data.last_hp = sol, board_txt, cur_hp
            content = (
                    "> 🔄 **Board changed! Re-calculated solution:**\n"
                    + ", ".join(m.upper() for m in sol)
                    + f"\n➡️ **Next:** **{sol[0].upper()}**"
            )
            if is_slash_dungeon(message):
                answer_msg = await (data.asking_msg.edit(content=content) if data.asking_msg else channel.send(content))
            else:
                answer_msg = await safe_send(channel, content)
            settings.DUNGEON15_LAST_ANSWER_MSG[cid] = answer_msg
            return

        # ATTACK step: handle win
        if expected == "attack":
            if "by infinity" in log_txt:
                reply = f"> 🎉 **VICTORY!** You’ve slain the dragon! {random.choice(RANDOM_EMOJIS)}"
                answer_msg = (
                    await data.asking_msg.edit(content=reply)
                    if slash_mode else await safe_send(channel, reply)
                )
                settings.DUNGEON15_HELPERS.pop(cid, None)
                settings.DUNGEON15_LAST_ANSWER_MSG[cid] = answer_msg
                return

            # Adjacency-based fallback win detection
            *_, drx, dry, bx, by, _, _ = process_board(data.last_board)
            if (abs(bx - drx) == 1 and by == dry) or (abs(by - dry) == 1 and bx == drx):
                reply = f"> 🎉 **CONGRATULATIONS!** {random.choice(RANDOM_EMOJIS)}"
                if is_slash_dungeon(message):
                    if data.asking_msg:
                        answer_msg = await data.asking_msg.edit(content=reply)
                    else:
                        answer_msg = await channel.send(reply)
                else:
                    answer_msg = await safe_send(channel, reply)
                settings.DUNGEON15_HELPERS.pop(cid, None)
                settings.DUNGEON15_LAST_ANSWER_MSG[cid] = answer_msg
                return

        # Advance solution to next move
        data.solution.pop(0)
        data.last_board, data.last_hp = board_txt, cur_hp
        if data.solution:
            nxt = data.solution[0].upper()
            rest = [m.upper() for m in data.solution[1:]]
            content = f"➡️ **Next:** **{nxt}**"
            if rest:
                content += "\n**UPCOMING:** " + ", ".join(rest)
            answer_msg = (
                await data.asking_msg.edit(content=content)
                if slash_mode else await safe_send(channel, content)
            )
            settings.DUNGEON15_LAST_ANSWER_MSG[cid] = answer_msg
        else:
            reply = f"> 🎉 **CONGRATULATIONS!** {random.choice(RANDOM_EMOJIS)}"
            answer_msg = (
                await data.asking_msg.edit(content=reply)
                if slash_mode else await safe_send(channel, reply)
            )
            settings.DUNGEON15_HELPERS.pop(cid, None)
            settings.DUNGEON15_LAST_ANSWER_MSG[cid] = answer_msg
        return

    # --- NEW SESSION: Find and send solution ---
    t0 = time.time()
    key = get_board_name_in_db(board_txt)
    sol = settings.d15_solutions.get(key, []).copy()
    if not sol or not verify_d15_solution(board_txt, cur_hp, sol):
        sol, _ = await solve_d15_c(board_txt, cur_hp)
    sol.append("attack")
    elapsed = f"{(time.time() - t0):.2f}s"

    text = (
            f"🧠 **Solution found!** ⏱ **{elapsed}**\n"
            + ", ".join(m.upper() for m in sol)
            + f"\n➡️ **Next:** **{sol[0].upper()}**"
    )
    if len(sol) > 1:
        text += "\n**UPCOMING:** " + ", ".join(m.upper() for m in sol[1:])

    if slash_mode:
        helper_msg = settings.NOTED_MESSAGE.pop(cid)
        await helper_msg.edit(content=text)
    else:
        helper_msg = await safe_send(channel, text)

    settings.DUNGEON15_HELPERS[cid] = D15Data(
        channel=channel,
        current_index=0,
        solution=sol,
        asking_msg=helper_msg,
        last_board=board_txt,
        last_hp=cur_hp,
    )
    settings.DUNGEON15_LAST_ANSWER_MSG[cid] = helper_msg

# --- Edit Handler ---

async def handle_d15_edit(payload) -> bool:
    """
    Handles D15 dungeon embed edits and updates the helper as needed.
    """
    if not payload.data.get("embeds"):
        return False
    if not is_d15_embed_edit(payload):
        return False

    author_id = int(payload.data.get("author", {}).get("id", 0))
    if author_id == settings.BOT_ID:
        return False

    chan = payload.channel_id
    channel = await settings.bot.fetch_channel(chan)
    message = await channel.fetch_message(payload.message_id)

    # Get last answer message for this channel
    answer_message = settings.DUNGEON15_LAST_ANSWER_MSG.get(chan)
    if not answer_message:
        answer_message = await find_last_bot_answer_message(channel, settings.BOT_ID, after_message_id=message.id)

    await handle_d15_message(
        message,
        from_new_message=False,
        bot_answer_message=answer_message
    )
    return True

# --- Ensure helper dicts exist at startup ---
if not hasattr(settings, "DUNGEON15_LAST_ANSWER_MSG"):
    settings.DUNGEON15_LAST_ANSWER_MSG = {}
if not hasattr(settings, "ALREADY_HANDLED_MESSAGES"):
    settings.ALREADY_HANDLED_MESSAGES = []
if not hasattr(settings, "LAST_D15_BOARD"):
    settings.LAST_D15_BOARD = {}