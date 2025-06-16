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
    def __init__(self, channel, current_index, solution, message, x, y, last_msg_id=None):
        self.channel = channel
        self.current_index = current_index
        self.solution = solution
        self.message = message
        self.x = x
        self.y = y
        self.last_msg_id = last_msg_id

def is_rate_limited(channel_id, message_id, cooldown=1.5):
    # Deduplication + cooldown (per channel/message)
    if not hasattr(settings, "_D12_EDIT_COOLDOWNS"):
        settings._D12_EDIT_COOLDOWNS = {}
    key = (channel_id, message_id)
    now = time.time()
    last = settings.D12_EDIT_COOLDOWNS.get(key, 0)
    if now - last < cooldown:
        return True
    settings.D12_EDIT_COOLDOWNS[key] = now
    if len(settings.D12_EDIT_COOLDOWNS) > 10000:
        settings.D12_EDIT_COOLDOWNS.clear()
    return False

def get_pos_from_moves(start_x, start_y, moves, up_to):
    x, y = start_x, start_y
    for move in moves[:up_to]:
        if move.upper() == 'UP':
            y -= 1
        elif move.upper() == 'DOWN':
            y += 1
        elif move.upper() == 'LEFT':
            x -= 1
        elif move.upper() == 'RIGHT':
            x += 1
    return x, y

def find_index_for_current_position(start_x, start_y, moves, player_x, player_y):
    for idx in range(len(moves)):
        x, y = get_pos_from_moves(start_x, start_y, moves, idx)
        if (x, y) == (player_x, player_y):
            return idx
    return 0  # fallback

async def handle_dungeon_12(
        embed: discord.Embed,
        channel: discord.TextChannel,
        from_new_message: bool,
        bot_answer_message: discord.Message = None,
        message: discord.Message = None,
):
    import traceback
    dungeon_id = channel.id
    event_msg_id = getattr(message, "id", 0)
    if is_rate_limited(channel.id, event_msg_id, cooldown=1.5):
        print(f"[D12] Rate limited on channel {channel.id} message {event_msg_id}")
        return

    print(f"[D12] ENTRY handle_dungeon_12: from_new_message={from_new_message}, channel={dungeon_id}")
    print(f"[D12] Current DUNGEON12_HELPERS state: {settings.DUNGEON12_HELPERS.get(dungeon_id)}")

    # Don't recursively re-enter! If message is missing, just clear state and exit
    if dungeon_id in settings.DUNGEON12_HELPERS:
        helper = settings.DUNGEON12_HELPERS[dungeon_id]
        if isinstance(helper, D12Data):
            msg = getattr(helper, "message", None)
            if not msg or not hasattr(msg, "id"):
                print(f"[D12] Helper state exists but no message. Resetting.")
                del settings.DUNGEON12_HELPERS[dungeon_id]
                return

    try:
        if embed.author.name and ' — dungeon' in embed.author.name:
            board_text = embed.fields[0].value.split("—\n\n:")[1]
            hp = int(embed.fields[0].value.split('** — :heart: ')[1].split('/')[0].replace(',', ''))
            hp_is_exact = True
        else:
            if dungeon_id in settings.DUNGEON12_HELPERS:
                del settings.DUNGEON12_HELPERS[dungeon_id]
            board_text = embed.fields[0].value
            hp = 901
            hp_is_exact = False

        try:
            board, y, x = d12_parse_full_board_and_pos(
                board_text,
                embed.fields[2].value.split('Currently on ')[1].split('\n')[0]
            )
            orbs = int(embed.fields[2].value.split('**Energy orbs**: ')[1].split('/')[0])
            quick_move = d12_check_win(board, y, x, orbs)
        except Exception as exc:
            print(f"[D12] Quick win/impossible check failed: {exc}")
            quick_move = None
            orbs = None

        if quick_move:
            msg_txt = f"> **Optimal move:** `{quick_move}` — you can win{' right now!' if quick_move == 'ATTACK' else ' in one move!'}"
            if is_slash_dungeon(message) if message else False:
                answer_msg = bot_answer_message or await channel.send(content=msg_txt)
                try:
                    await answer_msg.edit(content=msg_txt)
                except Exception:
                    answer_msg = await channel.send(content=msg_txt)
            else:
                answer_msg = await channel.send(content=msg_txt)
            return answer_msg

        if orbs is not None and (10 - orbs) * 55 >= hp:
            answer_msg = await channel.send(content=(
                f"> The dungeon is __**impossible**__ to win with your current HP. Please heal or get more max hp. "
                f"If you did a wrong move and you got this message, be more careful next time.\n\n"
                f"> __Why is it impossible to win???__\n"
                f"You lose -30 HP for every move you do (default dragon damage), and -25 HP "
                f"for every BLACK tile (+1 orb), so to reach 10 orbs you lose at least {(10-orbs)*55+30} HP. "
                f"You need 901HP for this dungeon."
            ))
            if dungeon_id in settings.DUNGEON12_HELPERS:
                del settings.DUNGEON12_HELPERS[dungeon_id]
            return answer_msg

        # Win detection
        win = await handle_d12_winning_embed(embed, channel, from_new_message)
        if win:
            return None

        # PLAN DEVIATION/REROUTE
        if dungeon_id in settings.DUNGEON12_HELPERS and isinstance(settings.DUNGEON12_HELPERS[dungeon_id], D12Data):
            data: D12Data = settings.DUNGEON12_HELPERS[dungeon_id]
            prev_x, prev_y = data.x, data.y
            prev_index = data.current_index
            dx, dy = x - prev_x, y - prev_y
            move_map = {(0, -1): 'UP', (0, 1): 'DOWN', (-1, 0): 'LEFT', (1, 0): 'RIGHT'}
            user_move = move_map.get((dx, dy))
            expected_move = None
            try:
                expected_move = data.solution[prev_index].upper()
            except Exception:
                pass
            print(f"[D12] Deviation Check: user_move={user_move}, expected_move={expected_move}")

            if user_move == expected_move:
                # Normal flow: advance plan
                data.current_index += 1
                data.x = x
                data.y = y
                move_preview_n = 3
                next_moves = [
                    data.solution[data.current_index + i].upper()
                    for i in range(move_preview_n)
                    if (data.current_index + i) < len(data.solution)
                ]
                moves_block = f"[{', '.join(next_moves)}]"
                content = f"> **Next moves:** {moves_block}"
                answer_msg = None
                try:
                    if is_slash_dungeon(message) if message else False:
                        answer_msg = data.message or bot_answer_message
                        await answer_msg.edit(content=content)
                    else:
                        answer_msg = await channel.send(content=content)
                except Exception:
                    answer_msg = await channel.send(content=content)
                    data.message = answer_msg
                    data.last_msg_id = event_msg_id
                return answer_msg
            else:
                print(f"[D12] PLAN DEVIATION detected, will reroute.")
                recalculating_txt = ":stop_sign: You deviated from the plan, recalculating optimal route from your new position!"
                reroute_id = random.randint(1, 100_000_000)
                settings.DUNGEON12_HELPERS[dungeon_id] = reroute_id

                try:
                    reroute_msg_final = await channel.send(content=recalculating_txt)
                except Exception as exc:
                    print(f"[D12] Could not send reroute message: {exc}")
                    reroute_msg_final = None

                try:
                    if data.message:
                        await data.message.edit(content="(Superseded: A new reroute is in progress. Please follow the latest bot message.)")
                except Exception:
                    pass

                if reroute_msg_final is None:
                    if dungeon_id in settings.DUNGEON12_HELPERS:
                        del settings.DUNGEON12_HELPERS[dungeon_id]
                    return None

                # SOLVER
                try:
                    board_for_solver = board_text
                    currently_on = embed.fields[2].value.split('Currently on ')[1].split('\n')[0]
                    orbs = int(embed.fields[2].value.split('**Energy orbs**: ')[1].split('/')[0])
                    hp = int(embed.fields[0].value.split('** — :heart: ')[1].split('/')[0].replace(',', ''))

                    solution, hp_lost, attempts, time_taken = await solve_d12_c(
                        reroute_msg_final, board_for_solver, currently_on, orbs, hp,
                        reroute_id, hp_is_exact=True
                    )
                except Exception as e:
                    print(f"[D12] Exception in reroute solver: {e}")
                    solution, attempts = [], 0

                if settings.DUNGEON12_HELPERS.get(dungeon_id) != reroute_id:
                    print("[D12] Reroute was superseded by another operation. Exiting reroute block.")
                    return None

                if attempts == -1 or attempts == 0:
                    fail_text = "> The dungeon is __**impossible**__ to win from this state. Please heal or restart."
                    try:
                        fail_msg = await channel.send(content=fail_text)
                        if hasattr(settings, "DUNGEON12_LAST_ANSWER_MSG"):
                            settings.DUNGEON12_LAST_ANSWER_MSG[channel.id] = fail_msg
                    except Exception as err:
                        print(f"[D12] Could not send fail reroute message: {err}")
                    del settings.DUNGEON12_HELPERS[dungeon_id]
                    return None

                solution += ['attack']
                move_list = [s.upper() for s in solution]
                moves_remaining = len(move_list) - 1
                upcoming_moves = " - ".join(move_list[:6])
                full_path_one_line = " ".join(move_list)
                solver_message_content = (
                    f"Moves remaining: {moves_remaining}\n"
                    f"Upcoming moves: {upcoming_moves} ...\n"
                    f"Full Solution Path: {hp_lost} HP\n"
                    f"```{full_path_one_line}```\n"
                )

                try:
                    solution_msg = await channel.send(content=solver_message_content)
                    if hasattr(settings, "DUNGEON12_LAST_ANSWER_MSG"):
                        settings.DUNGEON12_LAST_ANSWER_MSG[channel.id] = solution_msg
                except Exception as e:
                    print(f"[D12] Could not send reroute solution message: {e}")
                    solution_msg = None

                if solution_msg:
                    _, solver_y, solver_x = d12_parse_full_board_and_pos(board_for_solver, currently_on)
                    current_index = find_index_for_current_position(solver_x, solver_y, solution, x, y)
                    new_data = D12Data(channel, current_index, solution, solution_msg, x, y, last_msg_id=event_msg_id)
                    settings.DUNGEON12_HELPERS[dungeon_id] = new_data
                else:
                    del settings.DUNGEON12_HELPERS[dungeon_id]
                return solution_msg

        # --- Fresh solve ---
        currently_on = embed.fields[2].value.split('Currently on ')[1].split('\n')[0]
        orbs = int(embed.fields[2].value.split('**Energy orbs**: ')[1].split('/')[0])
        if (10 - orbs) * 55 >= hp:
            answer_msg = await channel.send(content=(
                f"> The dungeon is __**impossible**__ to win with your current HP. Please heal or get more max hp. "
                f"If you did a wrong move and you got this message, be more careful next time.\n\n"
                f"> __Why is it impossible to win???__\n"
                f"You lose -30 HP for every move you do (dragon), and -25 HP/black tile (+orb), so you lose {(10-orbs)*55+30} HP minimum."
            ))
            if dungeon_id in settings.DUNGEON12_HELPERS:
                del settings.DUNGEON12_HELPERS[dungeon_id]
            return answer_msg

        # Normal start: solution search
        try:
            if is_slash_dungeon(message) if message else False:
                if bot_answer_message:
                    await bot_answer_message.edit(content="I have started looking for a solution, please wait...")
                    asking_message = bot_answer_message
                else:
                    asking_message = await channel.send(content="I have started looking for a solution, please wait...")
            else:
                asking_message = await channel.send(content="I have started looking for a solution, please wait...")
        except Exception:
            asking_message = await channel.send(content="I have started looking for a solution, please wait...")

        solution_search_id = random.randint(1, 100_000_000)
        settings.DUNGEON12_HELPERS[dungeon_id] = solution_search_id

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
            asking_message, board_text, currently_on, orbs, hp,
            solution_search_id, hp_is_exact=hp_is_exact
        )

        if settings.DUNGEON12_HELPERS.get(dungeon_id) != solution_search_id:
            print("[D12] Search was superseded by another operation. Exiting.")
            return None

        if attempts == -1:
            if dungeon_id in settings.DUNGEON12_HELPERS:
                del settings.DUNGEON12_HELPERS[dungeon_id]
            return None

        if attempts == 0:
            await asking_message.edit(content=(
                f"> The dungeon is __**impossible**__ to win with your current HP. Please heal or get more max hp. "
                f"You need at least 901HP for this dungeon."
            ))
            del settings.DUNGEON12_HELPERS[dungeon_id]
            return asking_message

        solution += ['attack']
        move_list = [s.upper() for s in solution]
        moves_remaining = len(move_list) - 1
        upcoming_moves = " - ".join(move_list[:6])
        full_path_one_line = " ".join(move_list)
        solver_message_content = (
            f"Moves remaining: {moves_remaining}\n"
            f"Upcoming moves: {upcoming_moves} ...\n"
            f"Total Path is {hp_lost} HP\n"
            f"```{full_path_one_line}```\n"
        )
        try:
            if is_slash_dungeon(message) if message else False:
                answer_msg = bot_answer_message or asking_message
                await answer_msg.edit(content=solver_message_content)
            else:
                answer_msg = await channel.send(content=solver_message_content)
        except Exception:
            answer_msg = await channel.send(content=solver_message_content)

        new_data = D12Data(channel, 0, solution, answer_msg, x, y, last_msg_id=event_msg_id)
        settings.DUNGEON12_HELPERS[dungeon_id] = new_data
        return answer_msg

    except Exception:
        print("[D12] Exception in handle_dungeon_12")
        traceback.print_exc()
        return None


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
    from platform import system
    import time
    import asyncio

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
        # Stop if another solution was started (just mark as superseded, don't delete!)
        if initial_message.channel.id not in settings.DUNGEON12_HELPERS \
                or type(settings.DUNGEON12_HELPERS[initial_message.channel.id]) != int \
                or settings.DUNGEON12_HELPERS[initial_message.channel.id] != solution_search_id:
            kill_process(proc)
            try:
                await initial_message.edit(content="(Superseded: A new reroute/search started. Please follow the latest bot message.)")
            except Exception:
                pass  # Don't care if already deleted
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
def d12_check_win(board, y, x, orbs):
    """
    Returns:
      - 'ATTACK' if on white_large_square and have 10 orbs,
      - move direction if a move to a white_large_square would let you win in one,
      - None otherwise.
    board: list of tile_id strings ('0', '1', '2', '3', ...)
    y, x: current coords (0–2)
    orbs: current orb count (int)
    """
    if orbs >= 10 and board[y * 3 + x] == '3':
        return 'ATTACK'
    if orbs >= 10:
        directions = [(-1, 0, 'UP'), (1, 0, 'DOWN'), (0, -1, 'LEFT'), (0, 1, 'RIGHT')]
        for dy, dx, move in directions:
            ny, nx = y + dy, x + dx
            if 0 <= ny < 3 and 0 <= nx < 3 and board[ny * 3 + nx] == '3':
                return move
    return None

def d12_parse_full_board_and_pos(board_text, currently_on_text):
    # Returns board (flat list), y, x
    board_tiles = [x for x in board_text.split(':fire::fire::fire:\n')[1].split(':') if x in (
        'white_square_button', 'black_large_square', 'black_square_button', 'white_large_square',
        'ULTRAEDGYarmor', 'D12_ARMOR')]
    y = x = None
    out = []
    tile_ids = {
        'black_square_button': '0',
        'white_square_button': '1',
        'black_large_square': '2',
        'white_large_square': '3',
        'D12_ARMOR': '4',
        'ULTRAEDGYarmor': '4'
    }
    cur_id = tile_ids[currently_on_text.replace(':', '')]
    k = 0
    for i in range(3):
        for j in range(3):
            tid = tile_ids[board_tiles[k]]
            if tid == '4':
                y, x = i, j
                tid = cur_id
            out.append(tid)
            k += 1
    return out, y, x