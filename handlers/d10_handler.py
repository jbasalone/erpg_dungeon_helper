# handlers/d10_handler.py
# embed recognition

import discord
import settings
import dung_helpers
from utils_patch import safe_send
from utils_bot import is_channel_allowed, should_handle_edit

def is_d10_embed_msg(message: discord.Message) -> bool:
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    embed = message.embeds[0]
    embed_dict = embed.to_dict()
    fields = embed_dict.get("fields", [])
    title = embed_dict.get("title", "").lower()
    # Accept if 'edgy dragon' is in the title OR first field name
    if "edgy dragon" in title:
        return True
    if fields and "edgy dragon" in fields[0].get("name", "").lower():
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

async def handle_d10_message(
        message: discord.Message,
        *,
        is_edit: bool = None,
        from_new_message: bool = None
):
    """
    Handles both new D10 embeds (including the initial Edgy Dragon prompt)
    and edits to them. Compatible with dispatcher signature.
    """
    # Normalize edit state
    if is_edit is not None:
        edit = is_edit
    elif from_new_message is not None:
        edit = not from_new_message
    else:
        edit = False  # default to treating as new message

    # 1) Dedupe new embeds
    if not edit:
        if message.id in settings.ALREADY_HANDLED_MESSAGES:
            return
        settings.ALREADY_HANDLED_MESSAGES.append(message.id)
        if len(settings.ALREADY_HANDLED_MESSAGES) > 5000:
            settings.ALREADY_HANDLED_MESSAGES.clear()

    # 2) Permission check
    if not is_channel_allowed(message.channel.id, "d10", settings):
        return

    embed_dict = message.embeds[0].to_dict()
    channel = message.channel
    title = embed_dict.get("title", "").lower()
    fields = embed_dict.get("fields", [])
    author_name = embed_dict.get("author", {}).get("name", "") if "author" in embed_dict else ""

    # 3) Handle the initial Edgy Dragon prompt (no author, single field)
    if "edgy dragon" in title and len(fields) == 1:
        try:
            if not edit:
                helping = await channel.send("> 🔴 **CHARGE EDGY SWORD**")
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
            if not edit:
                helping = await safe_send("> 🔴 **CHARGE EDGY SWORD**")
                settings.DUNGEON10_HELPERS[channel.id] = dung_helpers.D10_data(helping)
            else:
                data = settings.DUNGEON10_HELPERS.get(channel.id)
                if data:
                    data.message = await data.message.edit(content="> 🔴 **CHARGE EDGY SWORD**")
            return
        except Exception as exc:
            print(f"[D10] Exception in fallback handling: {exc}")
            return

    # 4) Otherwise, parse combat embed
    try:
        attacker, defender, player = _parse_d10_names(embed_dict)
        data = settings.DUNGEON10_HELPERS.get(channel.id)
        if not data:
            return

        if player == attacker:
            content = f"> **{len(data.attacker_moves)+len(data.defender_moves)} 🔴 {data.attacker_moves.pop(0)}** ({attacker})"
        else:
            content = f"> **{len(data.attacker_moves)+len(data.defender_moves)} 🔵 {data.defender_moves.pop(0)}** ({defender})"
    except (KeyError, IndexError, Exception) as exc:
        print(f"[D10 Handler] Exception handler: {exc}")
        return

    try:
        if not edit:
            data.message = await safe_send(content)
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
    Raw -edit dispatcher for D10. Re-fetches the message and hands it off.
    """
    # 1) Is this the right embed?
    if not is_d10_embed_edit(payload):
        return False

    # 2) Skip our own edits
    author_id = int(payload.data.get("author",{}).get("id",0))
    if author_id == settings.BOT_ID:
        return False

    # 3) Permission / in-flight check
    if payload.channel_id not in settings.DUNGEON10_HELPERS and not should_handle_edit(payload, "d10"):
        return False

    # 4) Re-fetch & delegate
    try:
        channel = await settings.bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        await handle_d10_message(message, is_edit=True)
        return True
    except Exception as exc:
        print(f"[D10 Handler] Exception parsing names: {exc}")
        return False