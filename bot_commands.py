import discord
from utils_patch import should_process_message, safe_send, log_unmatched_embed

import settings
import re

valid_helpers = ('d10', 'd12', 'd13', 'd14', 'd15', 'd15.2', 'all')
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

async def help_command(channel: discord.TextChannel,
                       author: discord.User):
    embed = discord.Embed(colour=settings.EMBED_COLOR)
    embed.set_author(name=f"{author}'s dungeon help",
                     icon_url=author.avatar)

    embed.description = f"""> These are the dungeon helpers commands:
🔸You can both mention or use the channel/category ID in these commands.
🔸Use `d10`, `d13`, `d15.2` for the helpers. Use `all` for all of them at once

🔹`{settings.PREFIX} view [channel]` - view the helpers added in this channel
🔹`{settings.PREFIX} add [helper] [channel / category]` - add a helper in this channel or category.
🔹`{settings.PREFIX} remove [helper] [channel / category]` - remove a helper in this channel or category.
"""

    await safe_send(channel, embed=embed)


async def view_available_helpers_in_channel(channel: discord.TextChannel,
                                            author: discord.User,
                                            command: str):
    channel_to_send = channel

    channel_id = command.split()[-1].replace("<#", '').replace(">", '')

    if not channel_id.isnumeric() and channel_id != 'view':
        await safe_send(channel, f"{author.mention}, What are you trying to do? "
                                 f"Correct usage: `bs view [Channel]`. You can use the IDs or mention the channel.")
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