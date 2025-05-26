import asyncio
import random
import time
from platform import system

import discord

import settings
from dung_helpers import RANDOM_EMOJIS
from utils_bot import is_slash_dungeon

tile_ids = {
    'black_square_button': '0',
    'white_square_button': '1',
    'black_large_square': '2',
    'white_large_square': '3',
    'D12_ARMOR': '4',
    'ULTRAEDGYarmor': '4'
}

class D12Data:
    def __init__(self, channel, current_index, solution, message, x, y, required_hp: int, last_msg_id=None):
        self.channel: discord.TextChannel = channel
        self.current_index: int = current_index
        self.solution: list = solution
        self.message = message
        self.x = x
        self.y = y
        self.is_required_hp_fine = False
        self.required_hp = required_hp
        self.last_msg_id = last_msg_id

async def handle_dungeon_12(
        embed: discord.Embed,
        channel: discord.TextChannel,
        from_new_message: bool,
        bot_answer_message: discord.Message = None,
        message: discord.Message = None,
):
    # Parse board and HP
    if embed.author.name and ' — dungeon' in embed.author.name:
        board = embed.fields[0].value.split("—\n\n:")[1]
        hp = int(embed.fields[0].value.split('** — :heart: ')[1].split('/')[0].replace(',', ''))
        hp_is_exact = True
    else:
        if channel.id in settings.DUNGEON12_HELPERS:
            del settings.DUNGEON12_HELPERS[channel.id]
        board = embed.fields[0].value
        hp = 901
        hp_is_exact = False

    # Win detection
    win = await handle_d12_winning_embed(embed, channel, from_new_message)
    if win:
        return None

    dungeon_id = channel.id
    event_msg_id = getattr(message, "id", None)

    # If currently searching, warn user not to move
    if dungeon_id in settings.DUNGEON12_HELPERS and type(settings.DUNGEON12_HELPERS[dungeon_id]) == int:
        warning_key = f"d12_warn_{dungeon_id}"
        try:
            if not hasattr(settings, "DUNGEON12_WARNINGS"):
                settings.DUNGEON12_WARNINGS = {}
            warn_msg = settings.DUNGEON12_WARNINGS.get(warning_key)
            if warn_msg and not warn_msg.deleted:
                await warn_msg.edit(content=":stop_sign: I am recalculating, don't move!")
            else:
                warn_msg = await channel.send(":stop_sign: I am recalculating, don't move!")
                settings.DUNGEON12_WARNINGS[warning_key] = warn_msg
        except Exception as exc:
            print(f"[D12] Error sending recalculating warning: {exc}")
        return

    # Existing solver state: check move validity and preview next moves
    if dungeon_id in settings.DUNGEON12_HELPERS and isinstance(settings.DUNGEON12_HELPERS[dungeon_id], D12Data):
        data: D12Data = settings.DUNGEON12_HELPERS[dungeon_id]
        if data.last_msg_id is not None and event_msg_id is not None and event_msg_id < data.last_msg_id:
            print(f"[D12] Out-of-order message ignored: {event_msg_id} < {data.last_msg_id}")
            return

        board = embed.fields[0].value.split("—\n\n:")[1]
        new_y, new_x = get_x_y_d12(board)
        if new_x == data.x and new_y == data.y:
            return data.message

        # HP check before any move logic
        if not data.is_required_hp_fine:
            currently_on = embed.fields[2].value.split('Currently on ')[1].split('\n')[0]
            currently_on_tile_id = tile_ids[currently_on.replace(':', '')]
            before_hp = (
                (hp - 5) + 30 if currently_on_tile_id == '0' else
                hp + 500 + 30 if currently_on_tile_id == '1' else
                hp + 25 + 30 if currently_on_tile_id == '2' else
                hp + 30
            )
            if before_hp > data.required_hp:
                data.is_required_hp_fine = True
            else:
                content = "<:ep_greenleaf:1375735418292801567> Why you don't have the recommended 901HP for dungeon 12? The bot started looking for a new solution"
                try:
                    if from_new_message:
                        answer_msg = await channel.send(content=content)
                    else:
                        answer_msg = data.message or bot_answer_message
                        if answer_msg:
                            await answer_msg.edit(content=content)
                        else:
                            answer_msg = await channel.send(content=content)
                except Exception as exc:
                    print(f"[D12] Error editing message: {exc}")
                    answer_msg = await channel.send(content=content)
                if dungeon_id in settings.DUNGEON12_HELPERS:
                    del settings.DUNGEON12_HELPERS[dungeon_id]
                return answer_msg

        # -- MOVE HANDLING LOGIC --
        dx = new_x - data.x
        dy = new_y - data.y
        move_map = {(0, -1): 'UP', (0, 1): 'DOWN', (-1, 0): 'LEFT', (1, 0): 'RIGHT'}
        user_move = move_map.get((dx, dy))
        expected_move = None
        try:
            expected_move = data.solution[data.current_index].upper()
        except Exception:
            pass  # Only if index goes out of bounds

        print(f"[D12 DEBUG] User pos ({new_x},{new_y}) Prev pos ({data.x},{data.y}) User move: {user_move}, Expected: {expected_move}, Index: {data.current_index}")

        if user_move == expected_move:
            data.current_index += 1
            data.x = new_x
            data.y = new_y

            move_preview_n = 3
            next_moves = [
                data.solution[data.current_index + i].upper()
                for i in range(move_preview_n)
                if (data.current_index + i) < len(data.solution)
            ]
            moves_block = f"[{', '.join(next_moves)}]"
            content = f"> **Next moves:** {moves_block}"

            try:
                if is_slash_dungeon(message) if message else False:
                    answer_msg = data.message or bot_answer_message
                    await answer_msg.edit(content=content)
                else:
                    answer_msg = await channel.send(content=content)
            except Exception as exc:
                print(f"[D12] Error editing/sending message: {exc}")
                answer_msg = await channel.send(content=content)
            data.message = answer_msg
            data.last_msg_id = event_msg_id
            return answer_msg
        else:
            content = "<:ep_greenleaf:1375735418292801567> You messed up. I will try to find another solution. Be more careful!"
            try:
                if from_new_message:
                    answer_msg = await channel.send(content=content)
                else:
                    answer_msg = bot_answer_message or data.message
                    if answer_msg:
                        await answer_msg.edit(content=content)
                    else:
                        answer_msg = await channel.send(content=content)
            except Exception as exc:
                print(f"[D12] Error editing message: {exc}")
                answer_msg = await channel.send(content=content)
            if dungeon_id in settings.DUNGEON12_HELPERS:
                del settings.DUNGEON12_HELPERS[dungeon_id]
            print(f"[D12] Wrong move detected, recalculating solution...")
            # Do not return: lets new solver run immediately on next event

    # New run: initial checks and solution search
    currently_on = embed.fields[2].value.split('Currently on ')[1].split('\n')[0]
    orbs = int(embed.fields[2].value.split('**Energy orbs**: ')[1].split('/')[0])
    if (10 - orbs) * 55 >= hp:
        answer_msg = await channel.send(content=(
            f"> The dungeon is __**impossible**__ to win with your current HP. Please heal or get more max hp. "
            f"If you did a wrong move and you got this message, be more careful next time.\n\n"
            f"> __Why is it impossible to win???__\n"
            f"You lose -30 HP for every move you do (this is the default damage from the dragon), and you also lose -25 HP "
            f"for every BLACK tile you move to (this tile gives you +1 orb), this means "
            f"that you lose 55 hp for every orb collected. Considering you need {10 - orbs} more orbs, , so in order to reach 10 orbs you need to lose a MINIMUM of "
            f"{(10 - orbs) * 55 + 30} HP (in the best case scenario that won't happen). The best case scenario won't happen, you "
            f"need like 30-40% more than this value on average (because you won't always move to a black tile).\n\n"
            f"If you don't have the recommended 901HP of this dungeon, please get 901HP."
        ))
        if dungeon_id in settings.DUNGEON12_HELPERS:
            del settings.DUNGEON12_HELPERS[dungeon_id]
        return answer_msg

    # Initial "please wait" message
    try:
        if is_slash_dungeon(message) if message else False:
            if bot_answer_message:
                await bot_answer_message.edit(content="I have started looking for a solution, please wait...")
                asking_message = bot_answer_message
            else:
                asking_message = await channel.send(content="I have started looking for a solution, please wait...")
        else:
            asking_message = await channel.send(content="I have started looking for a solution, please wait...")
    except Exception as exc:
        print(f"[D12] Error sending initial wait message: {exc}")
        asking_message = await channel.send(content="I have started looking for a solution, please wait...")

    solution_search_id = random.randint(1, 100_000)
    settings.DUNGEON12_HELPERS[channel.id] = solution_search_id

    # Remove any recalculation warning for this channel (we are about to solve)
    warning_key = f"d12_warn_{channel.id}"
    if hasattr(settings, "DUNGEON12_WARNINGS"):
        warn_msg = settings.DUNGEON12_WARNINGS.get(warning_key)
        if warn_msg:
            try:
                await warn_msg.delete()
            except Exception:
                pass
            del settings.DUNGEON12_WARNINGS[warning_key]

    solution, hp_lost, attempts, time_taken = await solve_d12_c(
        asking_message, board, currently_on, orbs, hp,
        solution_search_id, hp_is_exact=hp_is_exact
    )

    if attempts == -1:
        if channel.id in settings.DUNGEON12_HELPERS:
            del settings.DUNGEON12_HELPERS[channel.id]
        return None

    if channel.id in settings.DUNGEON12_HELPERS:
        del settings.DUNGEON12_HELPERS[channel.id]

    if attempts == 0:
        await asking_message.edit(content=(
            f"> The dungeon is __**impossible**__ to win with your current HP. Please heal or get more max hp. "
            f"If you did a wrong move and you got this message, be more careful next time.\n\n"
            f"> __Why is it impossible to win???__\n"
            f"You lose -30 HP for every move you do (this is the default damage from the dragon), and you also lose -25 HP "
            f"for every BLACK tile you move to (this tile gives you +1 orb), this means "
            f"that you lose 55 hp for every orb collected. Considering you need {10 - orbs} more orbs, , so in order to reach 10 orbs you need to lose a MINIMUM of "
            f"{(10 - orbs) * 55 + 30} HP (in the best case scenario that won't happen). The best case scenario won't happen, you "
            f"need like 30-40% more than this value on average (because you won't always move to a black tile).\n\n"
            f"If you don't have the recommended 901HP of this dungeon, please get 901HP."
        ))
        return asking_message

    time_taken = f"{time_taken:.2f}"
    solution += ['attack']
    current_to_show = 0  # Always show preview from current move index

    move_preview_n = 3
    next_moves = [
        solution[current_to_show + i].upper()
        for i in range(move_preview_n)
        if (current_to_show + i) < len(solution)
    ]
    moves_block = f"[{', '.join(next_moves)}]"

    solver_message_content = (
        f"I found a solution!\n"
        f"♥ **Hp required:** {hp_lost}\n"
        f"⏱ **Solution found in:** {time_taken} seconds\n"
        f"🔀 **Attempts at solving:** {attempts:,}\n"
        f"🔢 **Total moves: ** {len(solution):,}\n"
        f"\n> **Next moves:** {moves_block}"
    )

    try:
        if from_new_message:
            answer_msg = await channel.send(content=solver_message_content)
        else:
            answer_msg = asking_message
            await answer_msg.edit(content=solver_message_content)
    except Exception as exc:
        print(f"[D12] Error final answer send/edit: {exc}")
        answer_msg = await channel.send(content=solver_message_content)

    y, x = get_x_y_d12(board)
    new_data = D12Data(channel, current_to_show, solution, answer_msg, x, y, hp_lost, last_msg_id=event_msg_id)
    new_data.is_required_hp_fine = hp_is_exact
    settings.DUNGEON12_HELPERS[channel.id] = new_data

    return answer_msg

async def handle_d12_winning_embed(embed: discord.Embed, channel: discord.TextChannel, from_new_message: bool):
    print("D12 HANDLER: Called with from_new_message =", from_new_message)
    if channel.id in settings.DUNGEON12_HELPERS and isinstance(settings.DUNGEON12_HELPERS[channel.id], D12Data):
        data: D12Data = settings.DUNGEON12_HELPERS[channel.id]
        print("D12 HANDLER: PASS VERIFICATION CHECK - Called with from_new_message =", from_new_message)
        if data is None:
            return True
        if "HAS KILLED THE OMEGA DRAGON" in embed.fields[0].value:
            content = f"> **CONGRATULATIONS!** {random.choice(RANDOM_EMOJIS)}"
            try:
                if from_new_message:
                    await channel.send(content=content)
                else:
                    await data.message.edit(content=content)
            except Exception as exc:
                print(f"[D12] Error on win message: {exc}")
                await channel.send(content=content)
            if channel.id in settings.DUNGEON12_HELPERS:
                del settings.DUNGEON12_HELPERS[channel.id]
            return True
    return False

def is_d12_embed(author_id: int, embed: discord.Embed):
    return (
            author_id in (settings.EPIC_RPG_ID, settings.UTILITY_NECROBOT_ID, settings.BETA_BOT_ID)
            and ((embed.author.name and ' — dungeon' in embed.author.name)
                 or (embed.title and 'YOU HAVE ENCOUNTERED **THE OMEGA DRAGON**' in embed.title))
            and embed.fields
            and ('D12_DRAGON' in embed.fields[0].name or 'OMEGAdragon' in embed.fields[0].name)
    )

def process_d12_board(board_text, currently_on_text):
    board = []
    board_tiles = [x for x in board_text.split(':fire::fire::fire:\n')[1].split(':') if x in (
        'white_square_button', 'black_large_square', 'black_square_button', 'white_large_square',
        'ULTRAEDGYarmor', 'D12_ARMOR')]
    Y, X = 0, 0
    x = 0
    for i in range(3):
        for j in range(3):
            tile_id = tile_ids[board_tiles[x]]
            if tile_id == '4':
                Y, X = i, j
                tile_id = tile_ids[currently_on_text.replace(':', '')]
            x += 1
            board.append(tile_id)
    return board, Y, X

def get_x_y_d12(board_text):
    board_tiles = [x for x in board_text.split(':fire::fire::fire:\n')[1].split(':') if x in (
        'white_square_button', 'black_large_square', 'black_square_button', 'white_large_square',
        'ULTRAEDGYarmor', 'D12_ARMOR')]
    x = 0
    for i in range(3):
        for j in range(3):
            if board_tiles[x] in ("D12_ARMOR", "ULTRAEDGYarmor"):
                return i, j
            x += 1
    return 0, 0

async def solve_d12_c(initial_message: discord.Message,
                      board_text: str,
                      currently_on_text: str,
                      orbs: int,
                      hp: int,
                      solution_search_id: int,
                      hp_is_exact=False):

    board, y, x = process_d12_board(board_text, currently_on_text)
    if system() == 'Linux':
        program = r"./dungeon_solvers/D12/D12_LINUX_SOLVER"
    else:
        program = r"./dungeon_solvers/D12/D12_HELPER.exe"
    start_time = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        program, *board, *[str(i) for i in (x, y, hp, orbs)],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    increase_hp_view = IncreaseHpView(hp)
    best_solution = []
    best_hp_lost = 0
    attempts = 0
    shown_increase_hp_view = False
    while True:
        await asyncio.sleep(0.2)
        # Stop if another solution was started
        if initial_message.channel.id not in settings.DUNGEON12_HELPERS \
                or type(settings.DUNGEON12_HELPERS[initial_message.channel.id]) != int \
                or settings.DUNGEON12_HELPERS[initial_message.channel.id] != solution_search_id:
            kill_process(proc)
            await initial_message.delete()
            return [], -1, -1, -1
        if increase_hp_view.time_passed >= 90:
            kill_process(proc)
            return [], 0, 0, 0
        if increase_hp_view.current_user_hp != hp:
            hp = increase_hp_view.current_user_hp
            kill_process(proc)
            await initial_message.edit(
                content=increase_hp_view.get_formatted_search_message(),
                view=increase_hp_view)
            proc = await asyncio.create_subprocess_exec(
                program, *board, *[str(i) for i in (x, y, hp, orbs)],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            continue
        # If the process returned something
        if proc.returncode is not None:
            solution, hp_lost, attempts = await process_d12_solution_output(proc)
            best_solution = solution
            best_hp_lost = hp_lost
            break
        increase_hp_view.time_passed = round(increase_hp_view.time_passed + 0.2, 2)
        if increase_hp_view.time_passed % 5 == 0 and not hp_is_exact:
            shown_increase_hp_view = True
            await initial_message.edit(
                content=increase_hp_view.get_formatted_search_message(),
                view=increase_hp_view)
        elif increase_hp_view.time_passed % 5 == 0 and hp_is_exact:
            await initial_message.edit(
                content=f"""> 🕓 - **{int(increase_hp_view.time_passed):.1f}s passed - Still searching for a solution...**
⚠ For dungeon 12, the recommended HP 901 ♥. 
**__NEVER__** start a dungeon 12 with less than 901HP. The chance that it will not be possible to win is high."""
            )

    if shown_increase_hp_view:
        await initial_message.edit(view=None)

    kill_process(proc)

    end_time = time.perf_counter()
    time_taken = round(end_time - start_time, 3)

    return best_solution, best_hp_lost, attempts, time_taken

def kill_process(proc):
    try:
        proc.kill()
    except ProcessLookupError:
        pass

async def process_d12_solution_output(proc):
    stdout, stderr = await proc.communicate()
    output = stdout.decode('UTF-8')

    solutions = [solution for solution in output.split("\n\n") if solution]
    solution = min(solutions, key=len).split('\n')[0].split()  # type: ignore

    attempts = int(solution.pop())
    hp_lost = int(solution.pop())

    return solution, hp_lost, attempts

class IncreaseHpView(discord.ui.View):
    def __init__(self, current_user_hp):
        super().__init__(timeout=None)
        self.current_user_hp = current_user_hp
        self.time_passed = 0

    def get_formatted_search_message(self):
        return f"""
> 🕓 - **{int(self.time_passed):.1f}s passed** - \
The bot searches for a solution, considering you have **{self.current_user_hp}HP ♥**.
If you have higher HP press the buttons below to increase it (faster to find a solution)"""

    @discord.ui.button(label="+10HP", emoji="♥", style=discord.ButtonStyle.green)
    async def a(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_user_hp += 10
        await interaction.message.edit(
            content=self.get_formatted_search_message(), view=self
        )

    @discord.ui.button(label="+100HP", emoji="♥", style=discord.ButtonStyle.green)
    async def b(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_user_hp += 100
        await interaction.message.edit(
            content=self.get_formatted_search_message(), view=self
        )