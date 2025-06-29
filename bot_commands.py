import discord
from utils_patch import should_process_message, safe_send, log_unmatched_embed

import settings
import re

valid_helpers = ('d10', 'd12', 'd13', 'd14', 'd15', 'd15.2', 'all')

async def add_all_helpers_to_channel(channel: discord.TextChannel, author: discord.User):
    for helper in valid_helpers[:-1]:  # Exclude "all"
        settings.allowed_channels[str(channel.id) + helper] = 1
    await safe_send(channel, f"{author.mention}, **all dungeon helpers have been ADDED** to {channel.mention}.")

async def remove_all_helpers_from_channel(channel: discord.TextChannel, author: discord.User):
    removed = False
    for helper in valid_helpers[:-1]:
        removed |= settings.allowed_channels.pop(str(channel.id) + helper, None) is not None
    if removed:
        await safe_send(channel, f"{author.mention}, **all dungeon helpers have been REMOVED** from {channel.mention}.")
    else:
        await safe_send(channel, f"{author.mention}, no helpers were enabled in {channel.mention}.")

def extract_helper_and_channel(raw_args, default_channel_id):
    valid_helpers = ('d10', 'd12', 'd13', 'd14', 'd15', 'd15.2', 'all')
    dungeon_helper = None
    channel_id = None

    for arg in raw_args:
        normalized = arg.lower().replace('-', '.').replace('_', '.')
        if normalized in valid_helpers and not dungeon_helper:
            dungeon_helper = normalized
        elif match := re.search(r'<#?(\d{5,})>?', arg):
            channel_id = match.group(1)
        elif re.fullmatch(r'\d{5,}', arg):
            channel_id = arg

    # If someone reversed order: like "gh add <#channel> d12"
    if not dungeon_helper and raw_args:
        for arg in raw_args:
            guess = arg.lower().replace('-', '.').replace('_', '.')
            if guess in valid_helpers:
                dungeon_helper = guess

    if not channel_id:
        channel_id = str(default_channel_id)

    return dungeon_helper, channel_id

async def help_command(channel: discord.TextChannel, author: discord.User):
    embed = discord.Embed(
        colour=settings.EMBED_COLOR,
        title="Dungeon Helpers — Command Reference",
        description=(
            "Easily manage and review dungeon helpers for your server.\n"
            "You can use **channel mentions** (e.g. `#general`), **category mentions** (e.g. `#my-category`), or numeric **IDs** in any command.\n\n"
            "**Supported helpers:** `d10`, `d12`, `d13`, `d14`, `d15`, `d15.2`, or `all` (for all dungeons).\n"
            "🔸 *Tip: Use `all` to add or remove every helper at once, for a channel or an entire category!*"
        )
    )
    embed.set_author(
        name=f"{author.display_name} — Dungeon Helpers Help",
        icon_url=getattr(author.avatar, "url", None) if hasattr(author, "avatar") else None
    )

    embed.add_field(
        name="🔍 View helpers in a channel",
        value=(
            f"`{settings.PREFIX} view [channel]`\n"
            "View which dungeon helpers are enabled in the current or specified channel.\n"
            f"• Example: `{settings.PREFIX} view #general`"
        ),
        inline=False,
    )

    embed.add_field(
        name="🗂️ List all enabled channels",
        value=(
            f"`{settings.PREFIX} enabled`\n"
            f"`{settings.PREFIX} list`\n"
            "Shows **all channels** in this server with at least one dungeon helper enabled."
        ),
        inline=False,
    )

    embed.add_field(
        name="✅ Add helpers",
        value=(
            f"`{settings.PREFIX} add [helper] [channel/category]`\n"
            "Enable a helper for a channel, or bulk-enable in every text channel of a category.\n"
            f"• Example (single): `{settings.PREFIX} add d14 #dungeon`\n"
            f"• Example (bulk): `{settings.PREFIX} add all #my-category`"
        ),
        inline=False,
    )

    embed.add_field(
        name="❌ Remove helpers",
        value=(
            f"`{settings.PREFIX} remove [helper] [channel/category]`\n"
            "Disable a helper for a channel, or remove from every text channel in a category.\n"
            f"• Example (single): `{settings.PREFIX} remove d15 #general`\n"
            f"• Example (bulk): `{settings.PREFIX} remove all #my-category`"
        ),
        inline=False,
    )

    embed.add_field(
        name="📋 Command Examples",
        value=(
            f"**View helpers in this channel:**\n"
            f"> `{settings.PREFIX} view`\n"
            f"**List all enabled channels:**\n"
            f"> `{settings.PREFIX} enabled`\n"
            f"**Add all helpers to a category:**\n"
            f"> `{settings.PREFIX} add all #dungeon-category`\n"
            f"**Remove d13 helper from a channel:**\n"
            f"> `{settings.PREFIX} remove d13 #general`\n"
            f"**Remove all helpers from a channel:**\n"
            f"> `{settings.PREFIX} remove all #general`"
        ),
        inline=False,
    )

    embed.set_footer(
        text="Only users with the allowed roles can use add/remove commands. Channels and categories can be mentioned or referenced by ID."
    )

    await safe_send(channel, embed=embed)

async def view_available_helpers_in_channel(channel: discord.TextChannel,
                                            author: discord.User,
                                            command: str):
    channel_to_send = channel

    channel_id = command.split()[-1].replace("<#", '').replace(">", '')

    if not channel_id.isnumeric() and channel_id != 'view':
        await safe_send(channel, f"{author.mention}, What are you trying to do? "
                                 f"Correct usage: `pd view [Channel]`. You can use the IDs or mention the channel.")
        return

    if channel_id == "view":
        channel_id = str(channel.id)

    channel = settings.bot.get_channel(int(channel_id))

    if not channel or channel.type == discord.ChannelType.category:
        channel_id = str(channel.id)
        channel = channel

    added_helpers = []
    for added_channel in settings.allowed_channels:
        if channel_id in added_channel:
            added_helpers.append(added_channel.replace(channel_id, ''))

    text = ""
    for helper in ('d10', 'd12', 'd13', 'd14', 'd15', 'd15.2'):
        if helper in added_helpers or settings.ALLOW_HELPERS_IN_ALL_CHANNELS:
            text += f"**{helper.upper()}** - ✅\n"
        else:
            text += f"**{helper.upper()}** - ❌\n"

    embed = discord.Embed(colour=0x6b655)
    embed.set_author(name=f"{author}'s helpers",
                     icon_url=author.avatar)
    embed.description = f"""> These are the dungeon helpers added in **#{channel.name}**:

    {text}
    View `{settings.PREFIX} help` to learn how to add more helpers or remove them."""

    await safe_send(channel_to_send, embed=embed)
    return


async def add_helper_to_channel(channel: discord.TextChannel,
                                author: discord.User,
                                command: str):

    raw_args = command.split()[1:]
    dungeon_helper, channel_id = extract_helper_and_channel(raw_args, channel.id)

    print(f"[DEBUG] raw_args: {raw_args}")
    print(f"[DEBUG] dungeon_helper: {dungeon_helper}, channel_id: {channel_id}")

    if dungeon_helper is None or dungeon_helper not in valid_helpers:
        await safe_send(channel,
                        f"{author.mention}, **INVALID DUNGEON HELPER** - Correct usage: `{settings.PREFIX} add [dungeon] [Channel / Category]`. Dungeon can be `d10`, `d12`, etc.")
        return

    if not channel_id.isnumeric():
        await safe_send(channel,
                        f"{author.mention}, **INVALID CHANNEL ID >>> {channel_id} <<<**")
        return

    channel_id = int(channel_id)
    target = settings.bot.get_channel(channel_id)

    if not target:
        await safe_send(channel,
                        f"{author.mention}, that channel or category couldn't be found.")
        return

    if target.type == discord.ChannelType.category:
        for chan in target.channels:
            for helper in valid_helpers[:-1] if dungeon_helper == 'all' else [dungeon_helper]:
                settings.allowed_channels[str(chan.id) + helper] = 1
        await safe_send(channel,
                        f"{author.mention}, successfully **ADDED** the **{dungeon_helper.upper()} helper(s)** to channels in **{target.name}**.")
    else:
        for helper in valid_helpers[:-1] if dungeon_helper == 'all' else [dungeon_helper]:
            settings.allowed_channels[str(target.id) + helper] = 1
        await safe_send(channel,
                        f"{author.mention}, successfully **ADDED** the **{dungeon_helper.upper()} helper(s)** to {target.mention}.")


async def remove_helper_from_channel(channel: discord.TextChannel,
                                     author: discord.User,
                                     command: str):

    raw_args = command.split()[1:]
    dungeon_helper, channel_id = extract_helper_and_channel(raw_args, channel.id)

    print(f"[DEBUG] raw_args: {raw_args}")
    print(f"[DEBUG] dungeon_helper: {dungeon_helper}, channel_id: {channel_id}")

    if dungeon_helper is None or dungeon_helper not in valid_helpers:
        await safe_send(channel,
                        f"{author.mention}, **INVALID DUNGEON HELPER** - Correct usage: `{settings.PREFIX} remove [dungeon] [Channel / Category]`. Dungeon can be `d10`, `d12`, etc.")
        return

    if not channel_id.isnumeric():
        await safe_send(channel,
                        f"{author.mention}, **INVALID CHANNEL ID >>> {channel_id} <<<**")
        return

    channel_id = int(channel_id)
    target = settings.bot.get_channel(channel_id)

    if not target:
        await safe_send(channel,
                        f"{author.mention}, that channel or category couldn't be found.")
        return

    if target.type == discord.ChannelType.category:
        for chan in target.channels:
            for helper in valid_helpers[:-1] if dungeon_helper == 'all' else [dungeon_helper]:
                settings.allowed_channels.pop(str(chan.id) + helper, None)
        await safe_send(channel,
                        f"{author.mention}, successfully **REMOVED** the **{dungeon_helper.upper()} helper(s)** from channels in **{target.name}**.")
    else:
        removed_any = False
        for helper in valid_helpers[:-1] if dungeon_helper == 'all' else [dungeon_helper]:
            removed_any |= settings.allowed_channels.pop(str(target.id) + helper, None) is not None
        if removed_any:
            await safe_send(channel,
                            f"{author.mention}, successfully **REMOVED** the **{dungeon_helper.upper()} helper(s)** from {target.mention}.")
        else:
            await safe_send(channel,
                            f"{author.mention}, that helper was not enabled in {target.mention}.")

    # --- NEW: Bulk add/remove for "add all"/"remove all" commands ---

async def add_all_helpers_to_channel_or_category(target, author: discord.User, channel_for_reply: discord.TextChannel):
    from discord import CategoryChannel, TextChannel
    if isinstance(target, CategoryChannel):
        count = 0
        for chan in target.channels:
            if chan.type == discord.ChannelType.text:
                for helper in valid_helpers[:-1]:
                    settings.allowed_channels[str(chan.id) + helper] = 1
                count += 1
        await safe_send(channel_for_reply, f"{author.mention}, **all dungeon helpers have been ADDED** to **{count} channels** in category **{target.name}**.")
    elif isinstance(target, TextChannel):
        for helper in valid_helpers[:-1]:
            settings.allowed_channels[str(target.id) + helper] = 1
        await safe_send(channel_for_reply, f"{author.mention}, **all dungeon helpers have been ADDED** to {target.mention}.")
    else:
        await safe_send(channel_for_reply, f"{author.mention}, invalid channel or category.")

async def remove_all_helpers_from_channel_or_category(target, author: discord.User, channel_for_reply: discord.TextChannel):
    from discord import CategoryChannel, TextChannel
    if isinstance(target, CategoryChannel):
        count = 0
        for chan in target.channels:
            if chan.type == discord.ChannelType.text:
                removed = False
                for helper in valid_helpers[:-1]:
                    removed |= settings.allowed_channels.pop(str(chan.id) + helper, None) is not None
                if removed:
                    count += 1
        await safe_send(channel_for_reply, f"{author.mention}, **all dungeon helpers have been REMOVED** from **{count} channels** in category **{target.name}**.")
    elif isinstance(target, TextChannel):
        removed = False
        for helper in valid_helpers[:-1]:
            removed |= settings.allowed_channels.pop(str(target.id) + helper, None) is not None
        if removed:
            await safe_send(channel_for_reply, f"{author.mention}, **all dungeon helpers have been REMOVED** from {target.mention}.")
        else:
            await safe_send(channel_for_reply, f"{author.mention}, no helpers were enabled in {target.mention}.")
    else:
        await safe_send(channel_for_reply, f"{author.mention}, invalid channel or category.")

async def list_enabled_channels_command(channel: discord.TextChannel, author: discord.User, guild):
    """
    Lists all text channels with at least one dungeon helper enabled.
    """
    # Reverse index: {channel_id: [d10, d12, ...]}
    from collections import defaultdict
    enabled = defaultdict(list)
    for key in settings.allowed_channels:
        # key format: "123456789012345678d13"
        match = re.fullmatch(r"(\d+)(d\d{2}(\.2)?)", key)
        if match:
            cid = int(match.group(1))
            helper = match.group(2)
            enabled[cid].append(helper)

    if not enabled:
        await safe_send(channel, f"{author.mention}, no dungeon helpers are enabled in any channels.")
        return

    lines = []
    for cid, helpers in enabled.items():
        chan = guild.get_channel(cid)
        if not chan:
            continue  # Channel might have been deleted
        helpers_fmt = ", ".join(h.upper() for h in helpers)
        lines.append(f"{chan.mention}: `{helpers_fmt}`")

    description = "\n".join(lines) if lines else "No dungeon helpers are enabled in any channels."
    embed = discord.Embed(
        title="Channels with Enabled Dungeon Helpers",
        description=description,
        colour=settings.EMBED_COLOR
    )
    embed.set_footer(text=f"Requested by {author.display_name}")

    await safe_send(channel, embed=embed)