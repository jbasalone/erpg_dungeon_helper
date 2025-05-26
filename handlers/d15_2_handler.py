# handlers/d15_2_handler.py

import discord
import time
import math
import random

import settings
import dung_helpers
from utils_patch import safe_send
from utils_bot import is_channel_allowed, should_handle_edit

DUNGEON15_2_LAST_BOARD = {}


def is_d15_2_embed_msg(message: discord.Message) -> bool:
    if not message.embeds:
        return False
    return dung_helpers.is_d15_2_embed(message.author.id, message.embeds[0].to_dict())

def is_d15_2_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    embeds = payload.data.get("embeds", [])
    if not embeds:
        return False
    author_id = int(payload.data.get("author", {}).get("id", 0))
    return dung_helpers.is_d15_2_embed(author_id, embeds[0])

async def handle_d15_2_message(message: discord.Message, from_new_message: bool = True):
    is_edit = not from_new_message
    """
    Handle both new D15.2 embeds and edits to them.
    Maintains state in settings.DUNGEON15_2_HELPERS.
    """
    # Deduplicate only new messages
    if not is_edit:
        if message.id in settings.ALREADY_HANDLED_MESSAGES:
            return
        settings.ALREADY_HANDLED_MESSAGES.append(message.id)
        if len(settings.ALREADY_HANDLED_MESSAGES) > 5000:
            settings.ALREADY_HANDLED_MESSAGES.clear()

    # Permission check
    if not is_channel_allowed(message.channel.id, "d15.2", settings):
        return

    # Remove any stale slash-dungeon marker for this channel
    settings.LAST_SLASH_DUNGEON_CALL.pop(message.channel.id, None)

    embed = message.embeds[0].to_dict()
    channel = message.channel

    # Use the "Map" field to represent board state
    board_str = None
    for f in embed.get("fields", []):
        if f.get("name", "").lower() == "map":
            board_str = f.get("value")
            break

    # Dedupe: Only act if board state changed
    if board_str:
        last_board = DUNGEON15_2_LAST_BOARD.get(channel.id)
        if last_board == board_str:
            print(f"[D15.2 DEBUG] Skipping duplicate board for channel {channel.id}")
            return
        DUNGEON15_2_LAST_BOARD[channel.id] = board_str

    # On fresh start (embed no longer looks like a dungeon), reset helper state
    if " — dungeon" not in embed.get("author", {}).get("name", ""):
        settings.DUNGEON15_2_HELPERS.pop(channel.id, None)

    # --- Continuing an existing session ---
    if channel.id in settings.DUNGEON15_2_HELPERS:
        data = settings.DUNGEON15_2_HELPERS[channel.id]

        # Congratulate and cleanup on boss fight end
        victory_strings = [
            "thought that getting healed while fighting",
            "the dragons killed each other",
            "has unlocked... the next area?",
            "new commands unlocked:"  # catch any new victory screens
        ]
        victory_found = any(
            s in (embed["fields"][0]["value"].lower() if embed.get("fields") and embed["fields"] else "")
            for s in victory_strings
        ) or (
                                "footer" in embed and embed["footer"].get("text") and
                                any(s in embed["footer"]["text"].lower() for s in victory_strings)
                        )
        if victory_found:
            await channel.send("> 🎉 **CONGRATULATIONS!** 🐉")
            settings.DUNGEON15_2_HELPERS.pop(channel.id, None)
            DUNGEON15_2_LAST_BOARD.pop(channel.id, None)
            return
        # Dizziness: reset if too many teleports, otherwise decay
        if "IS DIZZY AFTER TOO MANY TELEPORTS" in embed["fields"][0]["value"]:
            data.dizziness = 4
        if data.dizziness > 0:
            data.dizziness -= 1

        # First edit: latch dragon's max HP as 'coolness'
        if data.coolness == 0.001:
            try:
                hp_str = embed["fields"][0]["value"].split("**THE TIME DRAGON** — :purple_heart:")[-1]
                data.coolness = int(hp_str.split("/")[0])
            except Exception:
                data.coolness = 500

        # Calculate remaining heals (to_heal)
        try:
            seg = embed["fields"][0]["value"].split("**THE TIME DRAGON** — :purple_heart:")[-1]
            boss_max_hp = int(seg.split("/")[1].split("\n")[0]) - int(seg.split("/")[0])
        except Exception:
            boss_max_hp = 500

        delta = int((data.start_time + 1080) - time.time())
        minutes, seconds = divmod(max(delta, 0), 60)
        to_heal = math.ceil(boss_max_hp / data.coolness) if data.coolness else "?"

        # Next action (move)
        action = dung_helpers.process_D15_2_move(
            embed["fields"][1]["value"],
            data.coolness,
            data.dizziness
        )

        # Send/replace instructions
        data.message = await channel.send(
            f"**:clock1: Time left:** {minutes} min {seconds} sec\n"
            f":heart: **Heals left:** {to_heal}\n"
            f"> **{data.turn_number}.** **{action}**"
        )
        data.turn_number += 1
        return

    # --- New session: first embed seen ---
    fields = embed.get("fields", [])
    if len(fields) < 2:
        print("[D15.2 DEBUG] Not enough fields for action suggestion, probably a victory embed.")
        return
    action = dung_helpers.process_D15_2_move(fields[1]["value"], 0, 0)
    delta = 1080  # Always 18 minutes for fresh run
    minutes, seconds = divmod(delta, 60)
    helping_msg = await safe_send(
        channel,
        f"**:clock1: Time left:** {minutes} min {seconds} sec\n"
        f":heart: **Heals left:** ?\n"
        f"> **1.** **{action}**"
    )
    settings.DUNGEON15_2_HELPERS[channel.id] = dung_helpers.D15_2_Data(
        channel=channel,
        dizziness=0,
        coolness=0.001,
        start_time=time.time(),
        message=helping_msg,
        turn_number=2
    )

async def handle_d15_2_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    """Delegate raw-edit events back into the main D15.2 handler."""
    # Pattern match
    if not is_d15_2_embed_edit(payload):
        return False
    # Skip bot’s own edits
    if int(payload.data.get("author", {}).get("id", 0)) == settings.BOT_ID:
        return False
    # Permission logic: must be tracked or should_handle_edit allows
    if payload.channel_id not in settings.DUNGEON15_2_HELPERS and not should_handle_edit(payload, "d15.2"):
        return False
    # Fetch and dispatch
    chan = await settings.bot.fetch_channel(payload.channel_id)
    message = await chan.fetch_message(payload.message_id)
    await handle_d15_2_message(message, is_edit=True)
    return True