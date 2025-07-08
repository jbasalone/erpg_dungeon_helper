# handlers/d10_handler.py

import discord
import settings
import dung_helpers
from utils_patch import safe_send
from utils_bot import is_channel_allowed, should_handle_edit

def is_d10_embed_msg(message: discord.Message) -> bool:
    """Detect a brand-new D10 embed from EPIC RPG (but not D11)."""
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    embed = message.embeds[0].to_dict()
    fields = embed.get("fields", [])
    # D10: First field name always has "<:EDGYdragon:" but NOT "ULTRAEDGYdragon"
    if fields and fields[0]["name"].startswith("<:EDGYdragon:") \
            and "ULTRAEDGYdragon" not in fields[0]["name"]:
        # Additional: D10 typically doesn't have a "Map" as the second field
        return True
    return False

def is_d10_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    """Detect an edit of a D10 embed."""
    try:
        author_id = int(payload.data.get("author",{}).get("id",0))
        embeds = payload.data.get("embeds",[])
        if author_id != settings.EPIC_RPG_ID or not embeds:
            return False
        return dung_helpers.is_d10_embed(author_id, embeds[0])
    except Exception as exc:
        print(f"[D10 Handler] Exception detecting edit: {exc}")
        return False

async def handle_d10_message(message: discord.Message, *, is_edit: bool = None, from_new_message: bool = None):
    """
    Handles new messages (full message object).
    Delegates to the core handler using the embed.
    """
    embed = message.embeds[0]
    await handle_d10_message_from_embed(
        embed=embed,
        channel=message.channel,
        is_edit=is_edit if is_edit is not None else (not from_new_message)
    )

async def handle_d10_message_from_embed(
        embed: discord.Embed,
        channel: discord.TextChannel,
        *,
        is_edit: bool = False
):
    print(f"[D10 DEBUG] Got D10 embed in channel {channel.id}, edit={is_edit}")
    embed_dict = embed.to_dict()
    print(f"[D10 DEBUG] Embed title: {embed_dict.get('title')}")
    print(f"[D10 DEBUG] Embed author: {embed_dict.get('author',{}).get('name')}")
    print(f"[D10 DEBUG] Fields: {[f.get('name','') for f in embed_dict.get('fields',[])]}")

    # 1) Dedupe new embeds (not edits)
    if not is_edit:
        if hasattr(settings, "ALREADY_HANDLED_MESSAGES"):
            if getattr(channel, "last_message_id", None) in settings.ALREADY_HANDLED_MESSAGES:
                return
        if not hasattr(settings, "ALREADY_HANDLED_MESSAGES"):
            settings.ALREADY_HANDLED_MESSAGES = []
        if getattr(channel, "last_message_id", None):
            settings.ALREADY_HANDLED_MESSAGES.append(channel.last_message_id)
        if len(settings.ALREADY_HANDLED_MESSAGES) > 5000:
            settings.ALREADY_HANDLED_MESSAGES.clear()

    # 2) Permission check
    if not is_channel_allowed(channel.id, "d10", settings):
        return

    fields = embed_dict.get("fields", [])
    title = embed_dict.get("title", "").lower()
    author_name = embed_dict.get("author", {}).get("name", "") if "author" in embed_dict else ""

    # 3) Handle the initial Edgy Dragon prompt (no author, single field)
    if "edgy dragon" in title and len(fields) == 1:
        try:
            if not is_edit:
                helping = await channel.send("> 🔴 **CHARGE EDGY SWORD**")
                print(f"[D10 SEND] Sent CHARGE EDGY SWORD message: {helping}")
                settings.DUNGEON10_HELPERS[channel.id] = dung_helpers.D10_data(helping)
            else:
                data = settings.DUNGEON10_HELPERS.get(channel.id)
                if data:
                    data.message = await data.message.edit(content="> 🔴 **CHARGE EDGY SWORD**")
            return
        except Exception as exc:
            print(f"[D10] Exception in initial prompt handling: {exc}")
            return

    # 4) Otherwise, fallback to classic handling for multi-field embeds
    if not (author_name and ' — dungeon' in author_name):
        try:
            if not is_edit:
                helping = await safe_send(channel, "> 🔴 **CHARGE EDGY SWORD**")
                print(f"[D10 DEBUG] Sending move: {helping}")
                settings.DUNGEON10_HELPERS[channel.id] = dung_helpers.D10_data(helping)
            else:
                data = settings.DUNGEON10_HELPERS.get(channel.id)
                if data:
                    data.message = await data.message.edit(content="> 🔴 **CHARGE EDGY SWORD**")
            return
        except Exception as exc:
            print(f"[D10] Exception in fallback handling: {exc}")
            return

    # 5) Otherwise, parse combat embed
    try:
        attacker, defender, player = _parse_d10_names(embed_dict)
        data = settings.DUNGEON10_HELPERS.get(channel.id)
        if not data:
            return
        if player == attacker and data.attacker_moves:
            content = f"> **{len(data.attacker_moves)+len(data.defender_moves)} 🔴 {data.attacker_moves.pop(0)}** ({attacker})"
        elif data.defender_moves:
            content = f"> **{len(data.attacker_moves)+len(data.defender_moves)} 🔵 {data.defender_moves.pop(0)}** ({defender})"
        else:
            content = "> ⚠️ All moves exhausted for D10! (Bug?)"
            print(f"[D10 Handler] All moves exhausted for channel {channel.id}, cleaning up helper state.")
            settings.DUNGEON10_HELPERS.pop(channel.id, None)
    except (KeyError, IndexError, Exception) as exc:
        print(f"[D10 Handler] Exception handler: {exc}")
        return

    try:
        if not is_edit:
            data.message = await safe_send(channel, content)
            print(f"[D10 DEBUG] Sending move: {content}")
        else:
            await data.message.edit(content=content)
    except Exception as exc:
        print(f"[D10 Handler] Exception handle_d10: {exc}")
        return


def _parse_d10_names(embed: dict) -> tuple[str, str, str]:
    """
    Robustly extract attacker_name, defender_name, players_turn_name from embed fields.
    Will not crash if fields are missing or reordered.
    Returns (attacker, defender, player_turn)
    """
    fields = embed.get('fields', [])

    # Default fallback values
    attacker = defender = player = "Unknown"

    # 1. Get player whose turn it is
    if fields:
        # Example: "<:EDGYdragon:...> it's **ichigo271**'s turn!"
        turn_field = fields[0].get("name", "")
        if "it's **" in turn_field and "**'s turn" in turn_field:
            player = turn_field.split("it's **", 1)[-1].split("**'s turn", 1)[0].strip()
        else:
            player = "Unknown"

    # 2. Get attacker/defender from HP/status lines in the first field value
    # Search for lines with player names and hearts
    if fields:
        lines = fields[0].get("value", "").splitlines()
        heart_lines = [line for line in lines if "—" in line and ("purple_heart" in line or "yellow_heart" in line)]
        player_lines = [line for line in heart_lines if "**" in line]

        if player_lines and len(player_lines) >= 3:
            # Format: DRAGON, player1, player2
            attacker = player_lines[1].split("—")[0].replace("**", "").strip()
            defender = player_lines[2].split("—")[0].replace("**", "").strip()
        elif player_lines and len(player_lines) == 2:
            # Fallback if only two players
            attacker = player_lines[0].split("—")[0].replace("**", "").strip()
            defender = player_lines[1].split("—")[0].replace("**", "").strip()

    # Fallback if unable to parse, leave as "Unknown"
    return attacker, defender, player

async def handle_d10_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    """
    Raw -edit dispatcher for D10. No refetch! Use embed from payload.
    """
    if not is_d10_embed_edit(payload):
        return False
    author_id = int(payload.data.get("author",{}).get("id",0))
    if author_id == settings.BOT_ID:
        return False
    if payload.channel_id not in settings.DUNGEON10_HELPERS and not should_handle_edit(payload, "d10"):
        return False

    try:
        channel = await settings.bot.fetch_channel(payload.channel_id)
        embeds = payload.data.get("embeds", [])
        if not embeds:
            return False
        embed = discord.Embed.from_dict(embeds[0])
        await handle_d10_message_from_embed(
            embed=embed,
            channel=channel,
            is_edit=True
        )
        return True
    except Exception as exc:
        print(f"[D10 Handler] Exception in edit handler: {exc}")
        return False