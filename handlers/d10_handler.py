# handlers/d10_handler.py

import discord
import settings
import dung_helpers
from utils_patch import safe_send
from utils_bot import is_channel_allowed, should_handle_edit

def is_d10_embed_msg(message: discord.Message) -> bool:
    """Detect a brand-new D10 embed from EPIC RPG."""
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    return dung_helpers.is_d10_embed(message.author.id, message.embeds[0].to_dict())

def is_d10_embed_edit(payload: discord.RawMessageUpdateEvent) -> bool:
    """Detect an edit of a D10 embed."""
    try:
        author_id = int(payload.data.get("author",{}).get("id",0))
        embeds = payload.data.get("embeds",[])
        if author_id != settings.EPIC_RPG_ID or not embeds:
            return False
        return dung_helpers.is_d10_embed(author_id, embeds[0])
    except Exception as exc:
        # logger.error(f"[D10 Edit] Exception: {exc}")
        return False

async def handle_d10_message(message: discord.Message, *, is_edit: bool = False):
    """
    Handle both new D10 embeds and edits to them.
    If is_edit=False, we dedupe against ALREADY_HANDLED_MESSAGES.
    """
    # 1) Dedupe new embeds
    if not is_edit:
        if message.id in settings.ALREADY_HANDLED_MESSAGES:
            return
        settings.ALREADY_HANDLED_MESSAGES.append(message.id)
        if len(settings.ALREADY_HANDLED_MESSAGES) > 5000:
            settings.ALREADY_HANDLED_MESSAGES.clear()

    # 2) Permission check
    if not is_channel_allowed(message.channel.id, "d10", settings):
        return

    embed = message.embeds[0].to_dict()
    channel = message.channel

    # 3) If this is the pre-dungeon charge prompt…
    if not (message.embeds[0].author.name and ' — dungeon' in message.embeds[0].author.name):
        try:
            if not is_edit:
                helping = await channel.send("> 🔴 **CHARGE EDGY SWORD**")
                settings.DUNGEON10_HELPERS[channel.id] = dung_helpers.D10_data(helping)
            else:
                data = settings.DUNGEON10_HELPERS.get(channel.id)
                if data:
                    data.message = await data.message.edit(content="> 🔴 **CHARGE EDGY SWORD**")
            return
        except Exception as exc:
            # logger.error(f"[D10] Exception during charge prompt: {exc}")
            return

    # 4) Otherwise, parse combat embed
    try:
        attacker, defender, player = _parse_d10_names(embed)
        data = settings.DUNGEON10_HELPERS.get(channel.id)
        if not data:
            return

        if player == attacker:
            content = f"> **{len(data.attacker_moves)+len(data.defender_moves)} 🔴 {data.attacker_moves.pop(0)}** ({attacker})"
        else:
            content = f"> **{len(data.attacker_moves)+len(data.defender_moves)} 🔵 {data.defender_moves.pop(0)}** ({defender})"
    except (KeyError, IndexError, Exception) as exc:
        # logger.error(f"[D10] Exception during move parse: {exc}")
        return

    try:
        if not is_edit:
            data.message = await channel.send(content)
        else:
            await data.message.edit(content=content)
    except Exception as exc:
        # logger.error(f"[D10] Exception sending/editing message: {exc}")
        return

def _parse_d10_names(embed: dict) -> tuple[str, str, str]:
    """
    Helper to extract attacker_name, defender_name, players_turn_name from embed.fields.
    """
    val = embed['fields'][2]['value']
    attacker = val.split("'s edgy sword")[0].strip('*')
    defender = val.split("'s edgy sword")[1].split('\n')[-1].strip('*')
    player = embed['fields'][0]['name'].split(" it's **")[1].split("**'s turn!")[0].strip('*')
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
        # logger.error(f"[D10 Edit] Exception: {exc}")
        return False