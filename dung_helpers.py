import enum
import logging
import random
import subprocess
import time
import re
from platform import system

import discord
import asyncio
import threading

import settings
from utils_bot import is_slash_dungeon, d14_send

from dataclasses import dataclass, field
from typing import Optional, List, Any

from settings import (
    BOT_ID,
    ALLOW_HELPERS_IN_ALL_CHANNELS,
    DUNGEON10_HELPERS,
    DUNGEON11_HELPERS,
    DUNGEON12_HELPERS,
    DUNGEON13_HELPERS,
    DUNGEON14_HELPERS,
    DUNGEON15_HELPERS,
    DUNGEON15_2_HELPERS,
)


EPIC_RPG_ID = 555955826880413696
BETA_BOT_ID = 949425955653439509
D14_LAST_SENT_ACTION = {}
D14_LAST_DISPLAY = {} # channel_id: last_displayed_content
D14_PREV_MAP = {}

RANDOM_EMOJIS = "🎈🎆🎇🧨✨🎉🎊🎃🎄🎋🎍🎎🎏🎐🎑🧧🎀🎁🎗🎞🎟🎫🎠🎡🎡🛒🧶🧵🎨🖼🎭🎪🎢👓🕶🦺🥽🥼🧥👔👕❤🧡💛💚💙💜" \
                "🤎🖤🤍❣💕💞💓💗💖💘💝💟💌🍕🍔🍟🌭🍿🧂🥓🥚🥯🥨🥐🍞🧈🥞🧇🍳🥖🧀🥗🥙🥪🌮🌯🥫🍖🍗🥩🍠🥟🥠🥡🍱🍤" \
                "🍣🦪🍜🍛🍚🍙🍘🥝🥥🍇🍎🥭🍍🍌🍋🍊🍉🍈🍏🍐🍑🍒🍓🍅🍆🌽🍄🌶🥑🥒🥬🥦🥔🧄🌹🏵🌸💐🥜🌰🥕🧅🌺🌻🌼🌷" \
                "🥀☘🌱🌲🍂🍁🍀🌿🌵🌴🌳🌾"




class D13HelperData:
    def __init__(self):
        self.turn_number = 1
        self.previous_room_number = 0
        self.previous_dragon_room = 0
        self.last_answered_key = None  # Deduplication (room, dragon_room, question)
        self.message = None            # Last sent answer message (for edits)
        self.last_step = 1             # <-- Add this line!


def log_unmatched_embed(embed_dict):
    try:
        import json
        with open("unmatched_dungeon_embeds.log", "a") as log_file:
            log_file.write(json.dumps(embed_dict, indent=2) + "\n\n")
    except Exception:
        pass

""""
def get_answer(_type: str, question: str, left_answer, center_answer, right_answer):
    if question == "How many miliseconds have passed since you started this dungeon?":
        sorted_answers = [int(left_answer), int(center_answer), int(right_answer)]
        sorted_answers.sort()
        c, nsr, w = sorted_answers[1], sorted_answers[0], sorted_answers[2]

        if _type == "wrong":
            return str(w)
        elif _type == "not_so_wrong":
            return str(nsr)
        elif _type == "correct":
            return str(c)

    elif question == "How many arena cookies do you have right now?":
        sorted_answers = [int(left_answer), int(center_answer), int(right_answer)]
        sorted_answers.sort()

        c, nsr, w = sorted_answers

        if _type == "wrong":
            return str(w)
        elif _type == "not_so_wrong":
            return str(nsr)
        elif _type == "correct":
            return str(c)

    elif question == "What number am i thinking on right now?":
        sorted_answers = [int(left_answer), int(center_answer), int(right_answer)]
        sorted_answers.sort(reverse=True)

        c, nsr, w = sorted_answers

        if _type == "wrong":
            return str(w)
        elif _type == "not_so_wrong":
            return str(nsr)
        elif _type == "correct":
            return str(c)

    for possibe in D13_QUESTIONS:
        if possibe['question'] == question:
            return possibe[_type][0]

    return ''

"""
D13_QUESTIONS = [
    {
        'question': "Why does the wooden log tiers goes '...epic, super, mega, hyper...' while enchantments are '...mega, epic, hyper...'?",
        'correct': ("yes", 0), 'not_so_wrong': ("idk lol", 1), 'wrong': ("that's how the developer planned it", 2)},

    {'question': "`arcsin[4!+2*cos(0.02)/[(e^10)-log(4)^(π*π-111)]+10`",
     'correct': ("-5.3175", 0), 'not_so_wrong': ("-0.26399", 1), 'wrong': ("63.2217", 2)},

    {'question': "hi",
     'correct': ("hi >w<!!", 0), 'not_so_wrong': ("hi owo", 1), 'wrong': ("hi", 2)},

    {'question': "How was the 'duel' command used to be called?",
     'correct': ("pvp", 0), 'not_so_wrong': ("fight", 1), 'wrong': ("there was not a command like that", 2)},

    {'question': "What's the maximum level?",
     'correct': ("2147483647", 0), 'not_so_wrong': ("2389472895789437", 1), 'wrong': ("200", 2)},

    {'question': "What number am i thinking on right now?"},

    {'question': "Where can you get an epic fish?",
     'correct': ("Area 2+", 0), 'not_so_wrong': ("The river", 1), 'wrong': ("Area 1+", 2)},

    {'question': "How many coins do you start with?",
     'correct': ("250", 0), 'not_so_wrong': ("500", 1), 'wrong': ("0", 2)},

    {'question': "How many types of trainings are there?",
     'correct': ("5", 0), 'not_so_wrong': ("4", 1), 'wrong': ("1", 2)},

    {'question': "How many is the cap in time travels?",
     'correct': ("like very high", 0), 'not_so_wrong': ("10", 1), 'wrong': ("none", 2)},

    {'question': 'How many arena cookies do you have right now?'},

    {'question': "What's the minimum level required to craft an electronical armor?",
     'correct': ("20", 0), 'not_so_wrong': ("22", 1), 'wrong': ("24", 2)},

    {'question': "How many vehicles are there in EPIC RPG?",
     'correct': ("7", 0), 'not_so_wrong': ("4", 1), 'wrong': ("What? there's no vehicles", 2)},

    {'question': "Is this the best solo dungeon?",
     'correct': ("yes", 0), 'not_so_wrong': ("no, dungeon #12 was the best", 1),
     'wrong': ("no, dungeon #11 was the best", 2)},

    {'question': "How many miliseconds have passed since you started this dungeon?"}]



def get_answer(_type: str, question: str, left_answer, center_answer, right_answer):
    try:
        # Numeric sorting logic
        if question in [
            "How many miliseconds have passed since you started this dungeon?",
            "How many arena cookies do you have right now?"
        ]:
            answers = {
                "left": int(left_answer),
                "center": int(center_answer),
                "right": int(right_answer)
            }
            sorted_items = sorted(answers.items(), key=lambda x: x[1])
            if _type == "correct":
                return sorted_items[1][0]  # middle
            elif _type == "not_so_wrong":
                return sorted_items[0][0]  # lowest
            elif _type == "wrong":
                return sorted_items[2][0]  # highest

        elif question == "What number am i thinking on right now?":
            answers = {
                "left": int(left_answer),
                "center": int(center_answer),
                "right": int(right_answer)
            }
            sorted_items = sorted(answers.items(), key=lambda x: x[1], reverse=True)
            if _type == "correct":
                return sorted_items[0][0]  # highest
            elif _type == "not_so_wrong":
                return sorted_items[1][0]
            elif _type == "wrong":
                return sorted_items[2][0]

        # Direct lookup
        print(f"[D13 DEBUG] Searching for question: '{question}'")

        def clean(text):
            return text.lower().replace("*", "").replace("_", "").replace("`", "").strip()

        normalized_q = clean(question)
        for possible in D13_QUESTIONS:
            if clean(possible['question']) == normalized_q:
                expected, expected_index = possible.get(_type, (None, None))

                # Normalize options
                options = [left_answer.strip(), center_answer.strip(), right_answer.strip()]
                labels = ["left", "center", "right"]
                expected_clean = expected.strip().lower() if expected else ""

                print(f"[D13 MATCH] Question matched: {possible['question']}")
                print(f"[D13 ANSWER] Expecting: '{expected}' of type {_type}")

                for i, opt in enumerate(options):
                    if opt.lower() == expected_clean:
                        return labels[i]

                # Not found — try index fallback
                print(f"[D13 ERROR] Expected answer '{expected}' for type '{_type}' does not match any option:")
                print(f"            LEFT: '{left_answer}', CENTER: '{center_answer}', RIGHT: '{right_answer}'")

                if expected_index is not None and 0 <= expected_index < len(options):
                    print(f"[D13 FALLBACK] Using index fallback: returning {labels[expected_index]} (index {expected_index})")
                    return labels[expected_index]

                print(f"[D13 FALLBACK] No match or fallback index — returning 'right'")
                return "right"

    except Exception as e:
        print(f"[D13 ERROR] Failed to determine answer: {e}")

    return "right"

""""
def return_move(answer: str, left_answer, center_answer):
    return '⬅ LEFT' if answer == left_answer else '⬆ CENTER' if answer == center_answer else '➡ RIGHT'
"""
def return_move(answer: str, left_answer=None, center_answer=None, right_answer=None):
    if answer == "left":
        return f"⬅ LEFT ({left_answer})"
    elif answer == "center":
        return f"⬆ CENTER ({center_answer})"
    elif answer == "right":
        return f"➡ RIGHT ({right_answer})"
    else:
        return "❓ UNKNOWN"

async def get_d13_action(
        d13_data,
        room_number,
        dragon_room,
        previous_room_number,
        previous_dragon_room,
        question,
        left_answer,
        center_answer,
        right_answer
):
    messed_up_text = ''

    # --- Dynamically set phase/step based on current game state ---
    # Priority: Room 15+ -> Step 2; Dragon ≤ 8 -> Step 3; Room ≤ 8 -> Step 4; else Step 1

    # If user is "out of sync", recalculate last_step based on board state instead of always step 1
    new_step = 1
    if room_number >= 15:
        new_step = 2
    if dragon_room <= 8:
        new_step = 3
    if room_number <= 8:
        new_step = 4

    # Show a "messed up" message only if the step changed *backward* (i.e., user made a wrong move)
    if d13_data.last_step is not None and new_step < d13_data.last_step:
        messed_up_text = " (<:ep_greenleaf:1375735418292801567> recalculating from your current position because you messed up)"
    d13_data.last_step = new_step

    # Pick the right answer type for the new step
    if d13_data.last_step == 1:
        answer = get_answer('not_so_wrong', question, left_answer, center_answer, right_answer)
        return return_move(answer, left_answer, center_answer, right_answer) + messed_up_text
    elif d13_data.last_step == 2:
        answer = get_answer('wrong', question, left_answer, center_answer, right_answer)
        return return_move(answer, left_answer, center_answer, right_answer) + messed_up_text
    elif d13_data.last_step == 3:
        answer = get_answer('not_so_wrong', question, left_answer, center_answer, right_answer)
        return return_move(answer, left_answer, center_answer, right_answer) + messed_up_text
    elif d13_data.last_step == 4:
        answer = get_answer('correct', question, left_answer, center_answer, right_answer)
        return return_move(answer, left_answer, center_answer, right_answer) + messed_up_text

MOVE_EMOJI = {'LEFT': "⬅", "RIGHT": "➡", "UP": "⬆", "DOWN": "⬇", "ATTACK": "⚔", "PASS TURN": "🤚🏽"}


class D14ids(enum.Enum):
    PURPLE = 0
    BROWN = 1
    RED = 2
    BLUE = 3
    ORANGE = 4
    YELLOW = 5
    GREEN = 6
    ATTACK = 7
    DRAGON = 8


D14ids_TILES_DICT = {i.value: i.name for i in list(D14ids)}


def get_best_d14_start_move(MAP, X, Y):
    """
    For the starting map, it chooses the best move we can do and tells us what should be under the player
    """

    tiles_around_player = [-1, -1, -1, -1]

    if Y >= 2:
        tiles_around_player[0] = MAP[Y - 1][X]
    if Y < 7:
        tiles_around_player[1] = MAP[Y + 1][X]
    if X >= 1:
        tiles_around_player[2] = MAP[Y][X - 1]
    if X < 7:
        tiles_around_player[3] = MAP[Y][X + 1]

    if Y <= 4:
        order = [D14ids.BROWN.value, D14ids.GREEN.value,
                 D14ids.YELLOW.value, D14ids.ORANGE.value, D14ids.BLUE.value, D14ids.PURPLE.value, D14ids.RED.value]
    else:
        order = [D14ids.BROWN.value, D14ids.GREEN.value, D14ids.BLUE.value, D14ids.PURPLE.value,
                 D14ids.YELLOW.value, D14ids.ORANGE.value, D14ids.RED.value]

    move_to = {0: "UP", 1: "DOWN", 2: "LEFT", 3: "RIGHT"}
    for tile in order:
        if tile in tiles_around_player:
            return tile, move_to[tiles_around_player.index(tile)]


class BrownSearchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Take me to a brown tile!", emoji="🟫", style=discord.ButtonStyle.green)
    async def brown_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class HighHpSolutionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Follow solution", emoji="⭐", style=discord.ButtonStyle.green)
    async def brown_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


async def solve_d14_c(board, Y, X, HP, yellow_poison, orange_poison, inital_message: discord.Message):
    new_board = []
    for line in board:
        new_board += [str(i) for i in line]

    if system() == 'Linux':
        program = r"./dungeon_solvers/D14/D14_LINUX_SOLVER"
    else:
        program = "dungeon_solvers/D14/D14_HELPER_CODE.exe"

    # print(*new_board, *[str(i) for i in (Y, X, HP, yellow_poison, orange_poison)])

    start_time = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(program, *new_board,
                                                *[str(i) for i in (Y, X, HP, yellow_poison, orange_poison)],
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    is_next_to_alive_dragon = ((X == 1 and Y == 1 and board[0][1] == D14ids.DRAGON.value)
                               or (X == 6 and Y == 1 and board[0][6] == D14ids.DRAGON.value))

    # print(is_next_to_alive_dragon, board[0][1] == D14ids.DRAGON.value, board[0][6] == D14ids.DRAGON.value)

    time_passed = 0
    brown_view = BrownSearchView()
    hp_view = HighHpSolutionView()
    best_solution = []
    best_solution_tiles = []
    best_hp_lost = 0
    attempts = 0

    while True:
        await asyncio.sleep(0.5)

        # Only let the bot search 30s for the best solution
        if time_passed >= 30 and best_solution:
            break

        # If they liked the solution found, stop
        if hp_view.is_finished():
            break

        # If the process returned someting
        if proc.returncode is not None:
            real_solution, tiles_of_solution, attempts, hp_lost = await process_solution_output(proc)

            if not is_next_to_alive_dragon and len(real_solution) > 0 and real_solution[0] == 'ATTACK':

                proc = await asyncio.create_subprocess_exec(
                    program, *new_board,
                    *[str(i) for i in (Y, X, HP, yellow_poison, orange_poison)],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE)

            elif HP >= 2000:
                if not best_solution or (len(real_solution) < len(best_solution)) or (
                        len(best_solution) == len(real_solution) and hp_lost < best_hp_lost):
                    best_solution = real_solution
                    best_solution_tiles = tiles_of_solution
                    best_hp_lost = hp_lost

                    await inital_message.edit(content=f"""> <:ep_greenleaf:1375735418292801567> I am still looking for better solutions... [{time_passed} seconds passed]**

📶 **Best solution length: {len(best_solution)}**
❤ **HP Required: {best_hp_lost}**""", view=hp_view)

                proc = await asyncio.create_subprocess_exec(
                    program, *new_board,
                    *[str(i) for i in (Y, X, HP, yellow_poison, orange_poison)],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE)

            else:
                best_solution = real_solution
                best_solution_tiles = tiles_of_solution
                best_hp_lost = hp_lost
                break

        if time_passed >= 40:
            try:
                proc.kill()
            except ProcessLookupError:
                pass

            for child in brown_view.children:
                child.disabled = True
            await inital_message.edit(view=brown_view)

            return [], [], 0, 0, -1  # Return -1 so the go-to brown tile protocol begins

        if brown_view.is_finished():
            try:
                proc.kill()
            except ProcessLookupError:
                pass

            return [], [], 0, 0, -1  # Return -1 so the go-to brown tile protocol begins

        time_passed += 0.5
        if time_passed % 5 == 0 and not best_solution:
            await inital_message.edit(
                content=f"""> 🕓 - **{int(time_passed)} seconds passed** - [after 20 seconds it's recommended to go to a brown tile!]""",
                view=brown_view)

        elif time_passed % 5 == 0 and best_solution:
            await inital_message.edit(content=f"""> <:ep_greenleaf:1375735418292801567> I am still looking for better solutions... [{time_passed} seconds passed]**

📶 **Best solution length: {len(best_solution)}**
❤ **HP Required: {best_hp_lost}**""", view=hp_view)

    try:
        proc.kill()
    except ProcessLookupError:
        pass

    end_time = time.perf_counter()
    time_taken = round(end_time - start_time, 3)

    return best_solution, best_solution_tiles, attempts, best_hp_lost, time_taken

async def solve_d15_c(BOARD_TEXT: str, HP: int) -> tuple[list[str], int]:
    """
    Calls the D15 external solver and finds a valid solution sequence.
    Retries up to 200 attempts, verifies each result.
    Returns (solution, attempts).
    """
    X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, BOSSX, BOSSY, BOARD, MODE = process_board(BOARD_TEXT)
    if system() == 'Linux':
        program = "./dungeon_solvers/D15/D15_LINUX_SOLVER"
    else:
        program = "dungeon_solvers/D15/D15-2-Solver.exe"

    args = []
    for line in BOARD:
        for title in line:
            args.append(
                {"YELLOW": "0", "GREEN": "1", "RED": "2", "BLUE": "3"}.get(title, "0")
            )
    BOUND = str(HP - 18 if HP >= 152 else 4)
    args += [str(X), str(Y), str(CATX), str(CATY), str(DOGX), str(DOGY),
             str(DRAGONX), str(DRAGONY), str(BOSSX), str(BOSSY),
             str(MODE), str(HP), BOUND]

    attempts = 0
    MAX_ATTEMPTS = 200
    while attempts < MAX_ATTEMPTS:
        try:
            proc = await asyncio.create_subprocess_exec(
                program, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()
            stdout, stderr = await proc.communicate()
            output = stdout.decode('utf-8').strip()
            # Expect: move1, move2, ..., attempts:X or similar
            solution = [x for x in output.lower().split(", ") if x and not x.startswith("attempts:")]
            if verify_d15_solution(BOARD_TEXT, HP, solution):
                return solution, attempts
            if attempts % 5 == 0:
                await asyncio.sleep(0.05)
        except Exception as e:
            logging.exception(f"[D15 SOLVER ERROR] Attempt {attempts}: {e}")
            # If error, wait a bit and retry
            await asyncio.sleep(0.05)
        attempts += 1
    return [], attempts

async def process_solution_output(proc):
    stdout, stderr = await proc.communicate()

    output = stdout.decode('UTF-8')

    # print(output, stdout)
    solutions = [solution for solution in output.split("\n\n") if solution]
    solution = min(solutions, key=len).split('\n')[0].split()  # type: ignore

    attempts = int(solution.pop())
    hp_lost = int(solution.pop())
    real_solution = []
    tiles_of_solution = []

    for i, word in enumerate(solution):
        if not i % 2:
            real_solution.append(word)
        else:
            if real_solution[-1] == "ATTACK":
                tiles_of_solution.append("DRAGON")
            elif real_solution[-1] == "PASSTURN":
                tiles_of_solution.append("POGGERS")
                real_solution[-1] = "PASS TURN"
            else:
                tiles_of_solution.append(word)

    real_solution.append("ATTACK")
    tiles_of_solution.append("DRAGON")

    return real_solution, tiles_of_solution, attempts, hp_lost

def get_d14_map_data(current_embed, last_dungeon_embed, tile_we_moved_to):
    MAP = [[0 for _ in range(8)] for _ in range(8)]
    X, Y = 0, 0

    if 'title' in current_embed:
        MAP_TEXT = current_embed['fields'][0]['value']
        HP_LEFT = -1
    else:
        MAP_TEXT = current_embed['fields'][1]['value']
        HP_LEFT = int(current_embed['fields'][0]['value'].split(' — :heart: ')[1].split('/')[0].replace(",", ''))

    if last_dungeon_embed:
        if 'title' in last_dungeon_embed:
            OLD_MAP_TEXT = last_dungeon_embed['fields'][0]['value']
        else:
            OLD_MAP_TEXT = last_dungeon_embed['fields'][1]['value']

    MAP_TEXT = MAP_TEXT.replace('<', '').replace('>', '')
    for i in range(0, 10):
        MAP_TEXT = MAP_TEXT.replace(str(i), '')

    # D_DRAGON because we remove the numbers
    MAP_TEXT = MAP_TEXT.replace('D_DRAGON', 'GODLYdragon').replace('D_ARMOR', 'OMEGAarmor')
    MAP_TEXT = MAP_TEXT.split('\n')

    MAP_FIELDS = []
    for line in MAP_TEXT:
        MAP_FIELDS.append([i for i in line.split(":") if i])

    if last_dungeon_embed:
        OLD_MAP_TEXT = OLD_MAP_TEXT.replace('<', '').replace('>', '')
        for i in range(0, 10):
            OLD_MAP_TEXT = OLD_MAP_TEXT.replace(str(i), '')

        OLD_MAP_TEXT = OLD_MAP_TEXT.replace('D_DRAGON', 'GODLYdragon').replace('D_ARMOR', 'OMEGAarmor')
        OLD_MAP_TEXT = OLD_MAP_TEXT.split('\n')

        OLD_MAP_FIELDS = []
        for line in OLD_MAP_TEXT:
            OLD_MAP_FIELDS.append([i for i in line.split(":") if i])
    """
    0 - PURPLE
    1 - BROWN
    2 - RED
    3 - BLUE 
    4 - ORANGE
    5 - YELLOW
    6 - GREEN

    8 - DRAGON
    """
    for i, line in enumerate(MAP_FIELDS):
        for j, tile in enumerate(line):
            if tile == 'OMEGAarmor':
                MAP[i][j] = 0
                X, Y = j, i

            elif tile == 'GODLYdragon':
                MAP[i][j] = 8

            elif tile == 'purple_square':
                MAP[i][j] = 0
            elif tile == 'brown_square':
                MAP[i][j] = 1
            elif tile == 'red_square':
                MAP[i][j] = 2
            elif tile == 'blue_square':
                MAP[i][j] = 3
            elif tile == 'orange_square':
                MAP[i][j] = 4
            elif tile == 'yellow_square':
                MAP[i][j] = 5
            elif tile == 'green_square':
                MAP[i][j] = 6

    if last_dungeon_embed:
        if tile_we_moved_to == D14ids.PURPLE:
            MAP[Y][X] = D14ids.PURPLE

        elif tile_we_moved_to == D14ids.BROWN:
            MAP[Y][X] = D14ids.BLUE

        elif tile_we_moved_to == D14ids.RED:
            MAP[Y][X] = D14ids.RED

        elif tile_we_moved_to == D14ids.BLUE:
            MAP[Y][X] = D14ids.ORANGE - 1

        else:
            MAP[Y][X] = tile_we_moved_to

    return MAP, HP_LEFT, Y, X

async def get_dung_player(message):
    """For getting the last user that did rpg dung in a channel. For D15.1"""
    last_10_msg = message.channel.history(limit=100)
    async for msg in last_10_msg:
        if msg.content.lower() in ('rpg dung', 'rpg dungeon', 'pog d15 start'):
            return msg.author.id

    return 0


async def d15_2_start_time_left(message):
    """For getting the last user that did rpg dung in a channel. For D15.1"""
    last_10_msg = message.channel.history(limit=500)
    async for msg in last_10_msg:
        if msg.embeds:
            MESSAGE_EMBED = msg.embeds[0].to_dict()
            if (message.author.id in (EPIC_RPG_ID, BETA_BOT_ID)) \
                    and ('author' in MESSAGE_EMBED and " — dungeon" in MESSAGE_EMBED['author']['name']) \
                    and ('fields' in MESSAGE_EMBED and 'THE TIME DRAGON | turn' in MESSAGE_EMBED['fields'][0]['name']):
                if 'GOT FURIOUS BECAUSE' in MESSAGE_EMBED['fields'][0]['value']:
                    return msg.created_at.timestamp() + 10800

    return time.time()


async def get_last_d15_cmd(message):
    """For getting the last user that did rpg dung in a channel. For D15.1"""
    last_10_msg = message.channel.history(limit=10)
    async for msg in last_10_msg:
        if msg.content.lower() in (
                "up", "down", "left", "right", "attack", "dog", 'cat', 'dragon', 'switch', 'pass turn'):
            return msg

    return message


def is_move_valid(y, x, move):
    """Return True if the move is within map bounds (0-7)."""
    if move == "UP":
        return y > 0
    if move == "DOWN":
        return y < 7
    if move == "LEFT":
        return x > 0
    if move == "RIGHT":
        return x < 7
    return False


async def d13_helper(
        embed,
        channel,
        from_message,
        bot_answer_message=None,
        trigger_message=None,
        helpers=None,             # Add this (default None)
        message_based=False       # Add this (default False)
):
    """
    Universal D13 handler: supports both message-based (`rpg dungeon`) and slash (`/dungeon`) dungeons.
    For message-based: always sends a new message after each completed embed.
    For slash: edits the bot's answer message in place.
    """

    # -- Helper to check if this is a final, ready-to-answer embed (message-based)
    def is_final_rpg_dungeon_embed(embed):
        try:
            has_question = any(
                "QUESTION:" in (getattr(f, "name", "").upper() + getattr(f, "value", "").upper())
                for f in embed.fields
            )
            has_3_doors = (
                    sum(":door:" in getattr(f, "value", "") for f in embed.fields) >= 1
            )
            return has_question and has_3_doors
        except Exception:
            return False

    # ==== COMBAT CHECK ====
    combat_text = next(
        (f.value for f in embed.fields if "is in the same room as you" in f.value.lower()), None
    )
    if combat_text:
        if channel.id in DUNGEON13_HELPERS:
            data = DUNGEON13_HELPERS[channel.id]
            content = f"> **{data.turn_number}. ⚔ ATTACK**"
            if is_slash_dungeon(trigger_message):  # or use message in context
                await bot_answer_message.edit(content=content)
            else:
                await channel.send(content)
                del DUNGEON13_HELPERS[channel.id]
        else:
            await channel.send("> **1. ⚔ ATTACK**")
            try:
                data = D13HelperData()
                data.message = await channel.send("> **1. ⚔ ATTACK**")
            except Exception as e:
                print(f"[D13 BOT MSG ERROR] {e}")
        return

    # ==== QUESTION EXTRACTION ====
    question_field = next(
        (f for f in embed.fields if getattr(f, "name", "").strip().startswith("**QUESTION:**__")),
        None
    )
    if not question_field:
        question_field = next(
            (f for f in embed.fields if "QUESTION:" in getattr(f, "value", "").upper() and ":door:" in getattr(f, "value", "")),
            None
        )
    if not question_field:
        if is_slash_dungeon(trigger_message):
            await channel.send("❌ Could not parse question field.")
        return

    # ==== FINAL EMBED CHECK ====
    # Only respond if the message is ready (for message-based)
    if not is_slash_dungeon(trigger_message) and not is_final_rpg_dungeon_embed(embed):
        return

    # ==== ANSWER PARSING ====
    try:
        if "**QUESTION:**__" in question_field.name:
            question = question_field.name.replace("**QUESTION:**__", "").strip()
            lines = question_field.value.split(":door: :door: :door:\n")[1].split("\n")
        else:
            text = question_field.value
            question = text.split("QUESTION:")[1].split(":door:")[0].strip()
            lines = text.split(":door: :door: :door:\n")[1].split("\n")
        _, left_answer = lines[0].replace('*', '').split(": ", 1)
        _, center_answer = lines[1].replace('*', '').split(": ", 1)
        _, right_answer = lines[2].replace('*', '').split(": ", 1)
    except Exception as e:
        if is_slash_dungeon(trigger_message):
            await channel.send(f"❌ Failed to parse answers: {e}")
        return

    # ==== LOCATION EXTRACTION ====
    location_field = next(
        (f for f in embed.fields if "room:" in getattr(f, "value", "").lower() and "dragon" in getattr(f, "value", "").lower()),
        None
    )
    if not location_field:
        if is_slash_dungeon(trigger_message):
            await channel.send("❌ Could not find location field.")
        return

    try:
        location_value = location_field.value
        room_number = int(location_value.split("**ROOM:** `")[1].split("`\n")[0])
        dragon_room = int(location_value.split("ULTRA-OMEGA DRAGON** is ")[1].split()[0])
    except Exception as e:
        if is_slash_dungeon(trigger_message):
            await channel.send(f"❌ Failed to parse location: {e}")
        return

    # ==== STATE SETUP ====
    if channel.id not in DUNGEON13_HELPERS:
        data = D13HelperData()
        data.turn_number = 1
        data.last_answered_key = None
        data.previous_room_number = None
        data.previous_dragon_room = None
        DUNGEON13_HELPERS[channel.id] = data
    else:
        data = DUNGEON13_HELPERS[channel.id]

    # ==== DEDUPLICATION ====
    dedup_key = (room_number, dragon_room, question)
    if getattr(data, 'last_answered_key', None) == dedup_key:
        print(f"[D13 DEDUP] Already answered for {dedup_key}")
        return  # Already responded for this state

    # ==== GET ACTION ====
    action = await get_d13_action(
        data, room_number, dragon_room,
        data.previous_room_number, data.previous_dragon_room,
        question, left_answer, center_answer, right_answer
    )
    data.previous_room_number = room_number
    data.previous_dragon_room = dragon_room

    # ==== SEND OR EDIT ANSWER ====
    content = f"> **{data.turn_number}. {action}**"
    # Only edit for slash dungeons; always send new for message-based
    if is_slash_dungeon(trigger_message):  # or use message in context
        await bot_answer_message.edit(content=content)
    else:
        await channel.send(content)


    data.turn_number += 1
    data.last_answered_key = dedup_key
    DUNGEON13_HELPERS[channel.id] = data
    return data.message

def apply_d14_move(map_matrix, y, x, hp, move):
    """
    Simulate a single D14 move on a (deepcopied) map, returning the new y, x, and hp.
    - map_matrix: 8x8 list of lists (ints)
    - y, x: current position
    - hp: current HP (will NOT recalc poisons; you can extend)
    - move: string, e.g. "UP", "DOWN", "LEFT", "RIGHT", "PASS TURN", "ATTACK"
    Returns (y, x, hp)
    """

    # Make sure not to mutate original map
    from copy import deepcopy
    MAP = deepcopy(map_matrix)
    orig_y, orig_x = y, x

    if move == "UP" and y > 0:
        y -= 1
    elif move == "DOWN" and y < 7:
        y += 1
    elif move == "LEFT" and x > 0:
        x -= 1
    elif move == "RIGHT" and x < 7:
        x += 1
    elif move == "PASS TURN":
        hp = max(0, hp - 250)
    elif move == "ATTACK":
        # No movement; possibly affects dragon but not position
        pass
    # else: Invalid move, do nothing

    # (Optional) handle tile effects, e.g., landing on a tile, poison, heal, etc.
    # If you want to implement tile HP effects, add here using MAP[y][x].

    return y, x, hp

"""async def solve_d15_c(BOARD_TEXT, HP):
    X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, BOSSX, BOSSY, BOARD, MODE = process_board(BOARD_TEXT)
    if system() == 'Linux':
        command = "./dungeon_solvers/D15/D15_LINUX_SOLVER "
    else:
        command = "dungeon_solvers/D15/D15-2-Solver.exe "
    for line in BOARD:
        for title in line:
            command += {"YELLOW": "0 ", "GREEN": "1 ", "RED": "2 ", "BLUE": "3 "}.get(title, "0 ")
    BOUND = HP - 18 if HP >= 152 else 4
    command += f"{X} {Y} {CATX} {CATY} {DOGX} {DOGY} {DRAGONX} {DRAGONY} {BOSSX} {BOSSY} {MODE} {HP} {BOUND}"
    program, *args = command.split()
    attempts = 0
    MAX_ATTEMPTS = 200
    while attempts < MAX_ATTEMPTS:
        proc = await asyncio.create_subprocess_exec(program, *args,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
        await proc.wait()
        stdout, stderr = await proc.communicate()
        output = stdout.decode('utf-8').strip()
        solution = [x for x in output.lower().split(", ") if x and not x.startswith("attempts:")]
        if verify_d15_solution(BOARD_TEXT, HP, solution):
            return solution, attempts
        if attempts % 5 == 0:
            await asyncio.sleep(0.05)
        attempts += 1
    return [], attempts"""

def apply_move(board_text: str, move: str, HP: int) -> str:
    # 1) unpack
    X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, \
        BOSSX, BOSSY, BOARD, MODE = process_board(board_text)

    # 2) remember original floor colours
    tile_map = [row[:] for row in BOARD]

    # 3) your player move
    if move == "up":
        Y -= 2 if MODE else 1
    elif move == "down":
        Y += 2 if MODE else 1
    elif move == "left":
        X -= 2 if MODE else 1
    elif move == "right":
        X += 2 if MODE else 1
    elif move == "switch":
        MODE ^= 1
    elif move == "dog":
        X, DOGX = DOGX, X
        Y, DOGY = DOGY, Y
    elif move == "cat":
        X, CATX = CATX, X
        Y, CATY = CATY, Y
    elif move == "dragon":
        X, DRAGONX = DRAGONX, X
        Y, DRAGONY = DRAGONY, Y

    # 4) Time‐dragon reflection or dog‐jump behavior
    # 4a) Reflection if possible
    if 0 <= -(DRAGONX - X) + X <= 7 and 0 <= -(DRAGONY - Y) + Y <= 7:
        orig_dx, orig_dy = DRAGONX, DRAGONY
        DRAGONX = -(DRAGONX - X) + X
        DRAGONY = -(DRAGONY - Y) + Y
        # cancel if it would collide
        if (DRAGONX, DRAGONY) in {(X, Y), (CATX, CATY), (DOGX, DOGY), (BOSSX, BOSSY)}:
            DRAGONX, DRAGONY = orig_dx, orig_dy

    # 4b) Heavy‐HP color‐based dog-jump
    elif HP >= 131:
        color = BOARD[DOGY][DOGX]
        if color == "GREEN":
            DOGY = DOGY - 5 if DOGY >= 5 else min(7, DOGY + 2)
        elif color == "BLUE":
            DOGX = DOGX - 5 if DOGX >= 5 else min(7, DOGX + 2)
        elif color == "RED":
            DOGX = DOGX + 5 if DOGX <= 2 else max(0, DOGX - 2)
        elif color == "YELLOW":
            DOGY = DOGY + 5 if DOGY <= 2 else max(0, DOGY - 2)

    # 4c) Mid‐HP “shuffle” (dog↔cat then cat steps down)
    elif HP >= 101:
        DOGX, CATX = CATX, DOGX
        DOGY, CATY = CATY, DOGY
        for _ in range(3):
            if CATY < 7 and (CATY+1, CATX) not in {(X,Y),(DOGY,DOGX),(BOSSY,BOSSX),(DRAGONY,DRAGONX)}:
                CATY += 1
            else:
                break

    # 4d) Low‐HP retreat
    elif HP >= 61:
        for _ in range(3):
            if DOGY > 0 and (DOGY-1, DOGX) not in {(X,Y),(CATY,CATX),(BOSSY,BOSSX),(DRAGONY,DRAGONX)}:
                DOGY -= 1
            else:
                break

    # 4e) Very‐low‐HP fallback
    else:
        DOGX, DRAGONX = DRAGONX, DOGX
        DOGY, DRAGONY = DRAGONY, DOGY
        for _ in range(3):
            if CATX < 7 and (CATY, CATX+1) not in {(X,Y),(DOGY,DOGX),(BOSSY,BOSSX),(DRAGONY,DRAGONX)}:
                CATX += 1
            else:
                break

    # 5) single‐pass CAT movement toward player
    CAT_MOVE = 'NONE'
    dx, dy = X - CATX, Y - CATY
    if abs(dy) > abs(dx):
        CAT_MOVE = 'DOWN' if dy > 0 else 'UP'
    else:
        CAT_MOVE = 'RIGHT' if dx > 0 else 'LEFT'

    if CAT_MOVE == 'UP' and CATY > 0 and (CATY-1, CATX) not in {(X,Y),(DOGY,DOGX),(BOSSY,BOSSX),(DRAGONY,DRAGONX)}:
        CATY -= 1
    elif CAT_MOVE == 'DOWN' and CATY < 7 and (CATY+1, CATX) not in {(X,Y),(DOGY,DOGX),(BOSSY,BOSSX),(DRAGONY,DRAGONX)}:
        CATY += 1
    elif CAT_MOVE == 'LEFT' and CATX > 0 and (CATY, CATX-1) not in {(X,Y),(DOGY,DOGX),(BOSSY,BOSSX),(DRAGONY,DRAGONX)}:
        CATX -= 1
    elif CAT_MOVE == 'RIGHT' and CATX < 7 and (CATY, CATX+1) not in {(X,Y),(DOGY,DOGX),(BOSSY,BOSSX),(DRAGONY,DRAGONX)}:
        CATX += 1

    # 6) redraw the board
    color_to_emoji = {
        'RED':    ":red_square:",
        'BLUE':   ":blue_square:",
        'GREEN':  ":green_square:",
        'YELLOW': ":yellow_square:",
    }
    rows = []
    for i in range(8):
        row = []
        for j in range(8):
            if (i, j) == (BOSSY, BOSSX):
                row.append("<:TIMEdragon:707342275201728512>")
            elif (i, j) == (Y, X):
                row.append(
                    "<:ULTRAOMEGAarmor:707334203066417162>" if MODE == 0
                    else "<:ULTRAOMEGAsword:707334203066417162>"
                )
            elif (i, j) == (CATY, CATX):
                row.append("<:catpet:703150997517893692>")
            elif (i, j) == (DOGY, DOGX):
                row.append("<:dogpet:703152291540369450>")
            elif (i, j) == (DRAGONY, DRAGONX):
                row.append("<:dragonpet:705963075576135691>")
            else:
                row.append(color_to_emoji[tile_map[i][j]])
        rows.append("".join(row))

    return "\n".join(rows)

# noinspection PyTypeChecker
def verify_d15_solution(BOARD, HP, SEQUENCE):
    X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, BOSSX, BOSSY, BOARD, MODE = process_board(BOARD)

        # print_d15(X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, BOSSX, BOSSY, BOARD, MODE, HP, 'INITAL BOARD')
    for action in SEQUENCE:
        if action == 'switch':
            if MODE == 1:
                MODE = 0
            elif MODE == 0:
                MODE = 1

        elif action == 'up':
            if MODE == 0:
                Y -= 1
            elif MODE == 1:
                Y -= 2

        elif action == 'down':
            if MODE == 0:
                Y += 1
            elif MODE == 1:
                Y += 2

        elif action == 'left':
            if MODE == 0:
                X -= 1
            elif MODE == 1:
                X -= 2

        elif action == 'right':
            if MODE == 0:
                X += 1
            elif MODE == 1:
                X += 2

        elif action == 'dog':
            X, DOGX = DOGX, X
            Y, DOGY = DOGY, Y

        elif action == 'cat':
            X, CATX = CATX, X
            Y, CATY = CATY, Y

        elif action == 'dragon':
            X, DRAGONX = DRAGONX, X
            Y, DRAGONY = DRAGONY, Y

        if HP >= 131:
            if BOARD[0][0] == 'YELLOW':
                if BOARD[DOGY][DOGX] == 'GREEN':
                    if DOGY - 5 >= 0 and not (DOGY - 5 == Y and DOGX == X) and not (DOGY - 5 == CATY and DOGX == CATX) \
                            and not (DOGY - 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 5 == BOSSY and DOGX == BOSSX):
                        DOGY -= 5
                    elif DOGY + 2 <= 7 and not (DOGY + 2 == Y and DOGX == X) and not (DOGY + 2 == CATY and DOGX == CATX) \
                            and not (DOGY + 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 2 == BOSSY and DOGX == BOSSX):
                        DOGY += 2
                elif BOARD[DOGY][DOGX] == 'BLUE':
                    if DOGX - 5 >= 0 and not (DOGX - 5 == X and DOGY == Y) and not (DOGX - 5 == CATX and DOGY == CATY) \
                            and not (DOGX - 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 5 == BOSSX and DOGY == BOSSY):
                        DOGX -= 5
                    elif DOGX + 2 <= 7 and not (DOGX + 2 == X and DOGY == Y) and not (DOGX + 2 == CATX and DOGY == CATY) \
                            and not (DOGX + 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 2 == BOSSX and DOGY == BOSSY):
                        DOGX += 2
                elif BOARD[DOGY][DOGX] == 'RED':
                    if DOGX + 5 <= 7 and not (DOGX + 5 == X and DOGY == Y) and not (DOGX + 5 == CATX and DOGY == CATY) \
                            and not (DOGX + 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 5 == BOSSX and DOGY == BOSSY):
                        DOGX += 5
                    elif DOGX - 2 >= 0 and not (DOGX - 2 == X and DOGY == Y) and not (DOGX - 2 == CATX and DOGY == CATY) \
                            and not (DOGX - 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 2 == BOSSX and DOGY == BOSSY):
                        DOGX -= 2
                elif BOARD[DOGY][DOGX] == 'YELLOW':
                    if DOGY + 5 <= 7 and not (DOGY + 5 == Y and DOGX == X) and not (DOGY + 5 == CATY and DOGX == CATX) \
                            and not (DOGY + 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 5 == BOSSY and DOGX == BOSSX):
                        DOGY += 5
                    elif DOGY - 2 >= 0 and not (DOGY - 2 == Y and DOGX == X) and not (DOGY - 2 == CATY and DOGX == CATX) \
                            and not (DOGY - 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 2 == BOSSY and DOGX == BOSSX):
                        DOGY -= 2
                # ==========================================================================================
            elif BOARD[0][0] == 'GREEN':
                if BOARD[DOGY][DOGX] == 'BLUE':
                    if DOGY - 5 >= 0 and not (DOGY - 5 == Y and DOGX == X) and not (DOGY - 5 == CATY and DOGX == CATX) \
                            and not (DOGY - 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 5 == BOSSY and DOGX == BOSSX):
                        DOGY -= 5
                    elif DOGY + 2 <= 7 and not (DOGY + 2 == Y and DOGX == X) and not (DOGY + 2 == CATY and DOGX == CATX) \
                            and not (DOGY + 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 2 == BOSSY and DOGX == BOSSX):
                        DOGY += 2
                elif BOARD[DOGY][DOGX] == 'RED':
                    if DOGX - 5 >= 0 and not (DOGX - 5 == X and DOGY == Y) and not (DOGX - 5 == CATX and DOGY == CATY) \
                            and not (DOGX - 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 5 == BOSSX and DOGY == BOSSY):
                        DOGX -= 5
                    elif DOGX + 2 <= 7 and not (DOGX + 2 == X and DOGY == Y) and not (DOGX + 2 == CATX and DOGY == CATY) \
                            and not (DOGX + 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 2 == BOSSX and DOGY == BOSSY):
                        DOGX += 2
                elif BOARD[DOGY][DOGX] == 'GREEN':
                    if DOGX + 5 <= 7 and not (DOGX + 5 == X and DOGY == Y) and not (DOGX + 5 == CATX and DOGY == CATY) \
                            and not (DOGX + 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 5 == BOSSX and DOGY == BOSSY):
                        DOGX += 5
                    elif DOGX - 2 >= 0 and not (DOGX - 2 == X and DOGY == Y) and not (DOGX - 2 == CATX and DOGY == CATY) \
                            and not (DOGX - 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 2 == BOSSX and DOGY == BOSSY):
                        DOGX -= 2
                elif BOARD[DOGY][DOGX] == 'YELLOW':
                    if DOGY + 5 <= 7 and not (DOGY + 5 == Y and DOGX == X) and not (DOGY + 5 == CATY and DOGX == CATX) \
                            and not (DOGY + 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 5 == BOSSY and DOGX == BOSSX):
                        DOGY += 5
                    elif DOGY - 2 >= 0 and not (DOGY - 2 == Y and DOGX == X) and not (DOGY - 2 == CATY and DOGX == CATX) \
                            and not (DOGY - 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 2 == BOSSY and DOGX == BOSSX):
                        DOGY -= 2
                # ==========================================================================================
            elif BOARD[0][0] == 'RED':
                if BOARD[DOGY][DOGX] == 'RED':
                    if DOGY - 5 >= 0 and not (DOGY - 5 == Y and DOGX == X) and not (DOGY - 5 == CATY and DOGX == CATX) \
                            and not (DOGY - 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 5 == BOSSY and DOGX == BOSSX):
                        DOGY -= 5
                    elif DOGY + 2 <= 7 and not (DOGY + 2 == Y and DOGX == X) and not (DOGY + 2 == CATY and DOGX == CATX) \
                            and not (DOGY + 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 2 == BOSSY and DOGX == BOSSX):
                        DOGY += 2
                elif BOARD[DOGY][DOGX] == 'YELLOW':
                    if DOGX - 5 >= 0 and not (DOGX - 5 == X and DOGY == Y) and not (DOGX - 5 == CATX and DOGY == CATY) \
                            and not (DOGX - 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 5 == BOSSX and DOGY == BOSSY):
                        DOGX -= 5
                    elif DOGX + 2 <= 7 and not (DOGX + 2 == X and DOGY == Y) and not (DOGX + 2 == CATX and DOGY == CATY) \
                            and not (DOGX + 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 2 == BOSSX and DOGY == BOSSY):
                        DOGX += 2
                elif BOARD[DOGY][DOGX] == 'GREEN':
                    if DOGX + 5 <= 7 and not (DOGX + 5 == X and DOGY == Y) and not (DOGX + 5 == CATX and DOGY == CATY) \
                            and not (DOGX + 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 5 == BOSSX and DOGY == BOSSY):
                        DOGX += 5
                    elif DOGX - 2 >= 0 and not (DOGX - 2 == X and DOGY == Y) and not (DOGX - 2 == CATX and DOGY == CATY) \
                            and not (DOGX - 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 2 == BOSSX and DOGY == BOSSY):
                        DOGX -= 2
                elif BOARD[DOGY][DOGX] == 'BLUE':
                    if DOGY + 5 <= 7 and not (DOGY + 5 == Y and DOGX == X) and not (DOGY + 5 == CATY and DOGX == CATX) \
                            and not (DOGY + 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 5 == BOSSY and DOGX == BOSSX):
                        DOGY += 5
                    elif DOGY - 2 >= 0 and not (DOGY - 2 == Y and DOGX == X) and not (DOGY - 2 == CATY and DOGX == CATX) \
                            and not (DOGY - 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 2 == BOSSY and DOGX == BOSSX):
                        DOGY -= 2
                # ==========================================================================================
            elif BOARD[0][0] == 'BLUE':
                if BOARD[DOGY][DOGX] == 'RED':
                    if DOGY - 5 >= 0 and not (DOGY - 5 == Y and DOGX == X) and not (DOGY - 5 == CATY and DOGX == CATX) \
                            and not (DOGY - 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 5 == BOSSY and DOGX == BOSSX):
                        DOGY -= 5
                    elif DOGY + 2 <= 7 and not (DOGY + 2 == Y and DOGX == X) and not (DOGY + 2 == CATY and DOGX == CATX) \
                            and not (DOGY + 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 2 == BOSSY and DOGX == BOSSX):
                        DOGY += 2
                elif BOARD[DOGY][DOGX] == 'BLUE':
                    if DOGX - 5 >= 0 and not (DOGX - 5 == X and DOGY == Y) and not (DOGX - 5 == CATX and DOGY == CATY) \
                            and not (DOGX - 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 5 == BOSSX and DOGY == BOSSY):
                        DOGX -= 5
                    elif DOGX + 2 <= 7 and not (DOGX + 2 == X and DOGY == Y) and not (DOGX + 2 == CATX and DOGY == CATY) \
                            and not (DOGX + 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 2 == BOSSX and DOGY == BOSSY):
                        DOGX += 2
                elif BOARD[DOGY][DOGX] == 'YELLOW':
                    if DOGX + 5 <= 7 and not (DOGX + 5 == X and DOGY == Y) and not (DOGX + 5 == CATX and DOGY == CATY) \
                            and not (DOGX + 5 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX + 5 == BOSSX and DOGY == BOSSY):
                        DOGX += 5
                    elif DOGX - 2 >= 0 and not (DOGX - 2 == X and DOGY == Y) and not (DOGX - 2 == CATX and DOGY == CATY) \
                            and not (DOGX - 2 == DRAGONX and DOGY == DRAGONY) and not (
                            DOGX - 2 == BOSSX and DOGY == BOSSY):
                        DOGX -= 2
                elif BOARD[DOGY][DOGX] == 'GREEN':
                    if DOGY + 5 <= 7 and not (DOGY + 5 == Y and DOGX == X) and not (DOGY + 5 == CATY and DOGX == CATX) \
                            and not (DOGY + 5 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY + 5 == BOSSY and DOGX == BOSSX):
                        DOGY += 5
                    elif DOGY - 2 >= 0 and not (DOGY - 2 == Y and DOGX == X) and not (DOGY - 2 == CATY and DOGX == CATX) \
                            and not (DOGY - 2 == DRAGONY and DOGX == DRAGONX) and not (
                            DOGY - 2 == BOSSY and DOGX == BOSSX):
                        DOGY -= 2

            # CAT MOVEMENT
            CAT_MOVE = 'NONE'
            if DRAGONY < CATY and DRAGONX < CATX:
                if not (abs(DRAGONY - CATY) == 1 and abs(DRAGONX - CATX) == 1):
                    if abs(DRAGONY - CATY) < abs(DRAGONX - CATX):
                        CAT_MOVE = 'LEFT'
                    else:
                        CAT_MOVE = 'UP'

            elif DRAGONY > CATY and DRAGONX > CATX:
                if not (abs(DRAGONY - CATY) == 1 and abs(DRAGONX - CATX) == 1):
                    if abs(DRAGONY - CATY) < abs(DRAGONX - CATX):
                        CAT_MOVE = 'RIGHT'
                    else:
                        CAT_MOVE = 'DOWN'

            elif DRAGONY > CATY and DRAGONX < CATX:
                if not (abs(DRAGONY - CATY) == 1 and abs(DRAGONX - CATX) == 1):
                    if abs(DRAGONY - CATY) < abs(DRAGONX - CATX):
                        CAT_MOVE = 'LEFT'
                    else:
                        CAT_MOVE = 'DOWN'

            elif DRAGONY < CATY and DRAGONX > CATX:
                if not (abs(DRAGONY - CATY) == 1 and abs(DRAGONX - CATX) == 1):
                    if abs(DRAGONY - CATY) < abs(DRAGONX - CATX):
                        CAT_MOVE = 'RIGHT'
                    else:
                        CAT_MOVE = 'UP'

            elif CATX == DRAGONX and DRAGONY > CATY:
                CAT_MOVE = 'DOWN'
            elif CATX == DRAGONX and DRAGONY < CATY:
                CAT_MOVE = 'UP'
            elif CATY == DRAGONY and DRAGONX < CATX:
                CAT_MOVE = 'LEFT'
            elif CATY == DRAGONY and DRAGONX > CATX:
                CAT_MOVE = 'RIGHT'

            if CAT_MOVE == 'UP':
                if CATY - 1 >= 0 and not (CATY - 1 == DOGY and CATX == DOGX) and not (CATY - 1 == Y and CATX == X) and \
                        not (CATY - 1 == BOSSY and CATX == BOSSX) and not (CATY - 1 == DRAGONY and CATX == DRAGONX):
                    CATY -= 1

            elif CAT_MOVE == 'DOWN':
                if CATY + 1 <= 7 and not (CATY + 1 == DOGY and CATX == DOGX) and not (CATY + 1 == Y and CATX == X) and \
                        not (CATY + 1 == BOSSY and CATX == BOSSX) and not (CATY + 1 == DRAGONY and CATX == DRAGONX):
                    CATY += 1

            elif CAT_MOVE == 'RIGHT':
                if CATX + 1 <= 7 and not (CATX + 1 == DOGX and CATY == DOGY) and not (CATX + 1 == X and CATY == Y) and \
                        not (CATX + 1 == BOSSX and CATY == BOSSY) and not (CATX + 1 == DRAGONX and CATY == DRAGONY):
                    CATX += 1

            elif CAT_MOVE == 'LEFT':
                if CATX - 1 >= 0 and not (CATX - 1 == DOGX and CATY == DOGY) and not (CATX - 1 == X and CATY == Y) and \
                        not (CATX - 1 == BOSSX and CATY == BOSSY) and not (CATX - 1 == DRAGONX and CATY == DRAGONY):
                    CATX -= 1

            # DRAGON MOVEMENT
            if 0 <= -(DRAGONX - X) + X <= 7 and 0 <= -(DRAGONY - Y) + Y <= 7:
                INITIAL_X = DRAGONX
                INITIAL_Y = DRAGONY

                DRAGONX = -(DRAGONX - X) + X
                DRAGONY = -(DRAGONY - Y) + Y
                if CATY == DRAGONY and CATX == DRAGONX or BOSSY == DRAGONY and BOSSX == DRAGONX or \
                        DOGX == DRAGONX and DOGY == DRAGONY or X == DRAGONX and Y == DRAGONY:
                    DRAGONX = INITIAL_X
                    DRAGONY = INITIAL_Y

        elif HP >= 101:
            # DOG MOVEMENT
            DOGX, CATX = CATX, DOGX
            DOGY, CATY = CATY, DOGY
            # CAT MOVEMENT
            for i in range(3):
                if CATY + 1 <= 7 and not (CATY + 1 == DOGY and CATX == DOGX) and not (CATY + 1 == Y and CATX == X) and \
                        not (CATY + 1 == BOSSY and CATX == BOSSX) and not (CATY + 1 == DRAGONY and CATX == DRAGONX):
                    CATY += 1
                else:
                    break
            # DRAGON DOES NOTHING
        elif HP >= 61:
            # DOG MOVEMENT
            for i in range(3):
                if DOGY - 1 >= 0 and not (DOGY - 1 == CATY and DOGX == CATX) and not (DOGY - 1 == Y and DOGX == X) and \
                        not (DOGY - 1 == BOSSY and DOGX == BOSSX) and not (DOGY - 1 == DRAGONY and DOGX == DRAGONX):
                    DOGY -= 1
                else:
                    break
            # CAT MOVEMENT
            CAT_MOVE = 'NONE'

            if Y < CATY and X < CATX:
                if abs(Y - CATY) < abs(X - CATX):
                    CAT_MOVE = 'RIGHT'
                else:
                    CAT_MOVE = 'DOWN'
            elif Y > CATY and X > CATX:
                if abs(Y - CATY) < abs(X - CATX):
                    CAT_MOVE = 'LEFT'
                else:
                    CAT_MOVE = 'UP'

            elif Y > CATY and X < CATX:
                if abs(Y - CATY) < abs(X - CATX):
                    CAT_MOVE = 'RIGHT'
                else:
                    CAT_MOVE = 'UP'
            elif Y < CATY and X > CATX:
                if abs(Y - CATY) < abs(X - CATX):
                    CAT_MOVE = 'LEFT'
                else:
                    CAT_MOVE = 'DOWN'

            elif CATX == X and Y > CATY:
                CAT_MOVE = 'UP'
            elif CATX == X and Y < CATY:
                CAT_MOVE = 'DOWN'
            elif CATY == Y and X < CATX:
                CAT_MOVE = 'RIGHT'
            elif CATY == Y and X > CATX:
                CAT_MOVE = 'LEFT'

            if CAT_MOVE == 'UP':
                if CATY - 1 >= 0 and not (CATY - 1 == DOGY and CATX == DOGX) and not (
                        CATY - 1 == Y and CATX == X) and \
                        not (CATY - 1 == BOSSY and CATX == BOSSX) and not (
                        CATY - 1 == DRAGONY and CATX == DRAGONX):
                    CATY -= 1
            elif CAT_MOVE == 'DOWN':
                if CATY + 1 <= 7 and not (CATY + 1 == DOGY and CATX == DOGX) and not (
                        CATY + 1 == Y and CATX == X) and \
                        not (CATY + 1 == BOSSY and CATX == BOSSX) and not (
                        CATY + 1 == DRAGONY and CATX == DRAGONX):
                    CATY += 1
            elif CAT_MOVE == 'RIGHT':
                if CATX + 1 <= 7 and not (CATX + 1 == DOGX and CATY == DOGY) and not (
                        CATX + 1 == X and CATY == Y) and \
                        not (CATX + 1 == BOSSX and CATY == BOSSY) and not (
                        CATX + 1 == DRAGONX and CATY == DRAGONY):
                    CATX += 1
            elif CAT_MOVE == 'LEFT':
                if CATX - 1 >= 0 and not (CATX - 1 == DOGX and CATY == DOGY) and not (
                        CATX - 1 == X and CATY == Y) and \
                        not (CATX - 1 == BOSSX and CATY == BOSSY) and not (
                        CATX - 1 == DRAGONX and CATY == DRAGONY):
                    CATX -= 1

            # DRAGON MOVEMENT
            if 0 <= -(DRAGONX - 4) + 3 <= 7 and 0 <= -(DRAGONY - 4) + 3 <= 7:
                INITIAL_X = DRAGONX
                INITIAL_Y = DRAGONY
                DRAGONX = -(DRAGONX - 4) + 3
                DRAGONY = -(DRAGONY - 4) + 3
                if CATY == DRAGONY and CATX == DRAGONX or BOSSY == DRAGONY and BOSSX == DRAGONX or \
                        DOGX == DRAGONX and DOGY == DRAGONY or X == DRAGONX and Y == DRAGONY:
                    DRAGONX = INITIAL_X
                    DRAGONY = INITIAL_Y
        else:
            # DOG MOVEMENT
            DOGX, DRAGONX = DRAGONX, DOGX
            DOGY, DRAGONY = DRAGONY, DOGY
            # CAT MOVEMENT
            for i in range(3):
                if CATX + 1 <= 7 and not (CATX + 1 == DOGX and CATY == DOGY) and not (CATX + 1 == X and CATY == Y) and \
                        not (CATX + 1 == BOSSX and CATY == BOSSY) and not (CATX + 1 == DRAGONX and CATY == DRAGONY):
                    CATX += 1
                else:
                    break
            # DRAGON MOVEMENT
            for i in range(3):
                if DRAGONX - 1 >= 0 and not (DRAGONX - 1 == DOGX and DRAGONY == DOGY) and not (
                        DRAGONX - 1 == X and DRAGONY == Y) and \
                        not (DRAGONX - 1 == BOSSX and DRAGONY == BOSSY) and not (
                        DRAGONX - 1 == CATX and DRAGONY == CATY):
                    DRAGONX -= 1
                else:
                    break

        for i, line in enumerate(BOARD):
            for j, title in enumerate(line):
                if title == 'RED':
                    BOARD[i][j] = 'BLUE'
                elif title == 'GREEN':
                    BOARD[i][j] = 'RED'
                elif title == 'YELLOW':
                    BOARD[i][j] = 'GREEN'
                elif title == 'BLUE':
                    BOARD[i][j] = 'YELLOW'

               # print_d15(X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, BOSSX, BOSSY, BOARD, MODE, HP, action)

    if ((BOSSY - 1 == Y and BOSSX == X) or (BOSSY - 1 == CATY and BOSSX == CATX) or (
            BOSSY - 1 == DOGY and BOSSX == DOGX) or (BOSSY - 1 == DRAGONY and BOSSX == DRAGONX)) and \
            ((BOSSY + 1 == Y and BOSSX == X) or (BOSSY + 1 == CATY and BOSSX == CATX) or (
                    BOSSY + 1 == DOGY and BOSSX == DOGX) or (BOSSY + 1 == DRAGONY and BOSSX == DRAGONX)) and \
            ((BOSSX - 1 == X and BOSSY == Y) or (BOSSX - 1 == CATX and BOSSY == CATY) or (
                    BOSSX - 1 == DOGX and BOSSY == DOGY) or (BOSSX - 1 == DRAGONX and BOSSY == DRAGONY)) and \
            ((BOSSX + 1 == X and BOSSY == Y) or (BOSSX + 1 == CATX and BOSSY == CATY) or (
                    BOSSX + 1 == DOGX and BOSSY == DOGY) or (BOSSX + 1 == DRAGONX and BOSSY == DRAGONY)):
        return True
    else:
        return False


def get_board_name_in_db(BOARD_TEXT):
    X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, BOSSX, BOSSY, _, _ = process_board(BOARD_TEXT)
    return f"{X}{Y}{CATX}{CATY}{DOGX}{DOGY}{DRAGONX}{DRAGONY}{BOSSX}{BOSSY}"


def run_simulation(coordonates, BOARD):
    ALLOWED_MOVEMENTS = []
    OUTCOMES = {}
    X, Y, BOSSX, BOSSY = coordonates

    # ADDING THE ALLOWED MOVEMENTS
    if Y > 0 and not (BOSSX == X and BOSSY == Y - 1):
        ALLOWED_MOVEMENTS.append('up')
    if Y < 7 and not (BOSSX == X and BOSSY == Y + 1):
        ALLOWED_MOVEMENTS.append('down')
    if X > 0 and not (BOSSX == X - 1 and BOSSY == Y):
        ALLOWED_MOVEMENTS.append('left')
    if X < 7 and not (BOSSX == X + 1 and BOSSY == Y):
        ALLOWED_MOVEMENTS.append('right')
    if (X == BOSSX and Y == BOSSY - 1) or (X == BOSSX and Y == BOSSY + 1) or (X == BOSSX - 1 and Y == BOSSY) or (
            X == BOSSX + 1 and Y == BOSSY):
        ALLOWED_MOVEMENTS.append('heal')

    for action in ALLOWED_MOVEMENTS:
        X, Y, BOSSX, BOSSY = coordonates
        PLAYER_HEALED = False
        DRAGON_HEALED = False
        HEAL = False

        if action == 'up':
            if Y > 0 and not (BOSSX == X and BOSSY == Y - 1):
                Y -= 1
                if BOARD[Y][X] == 2:
                    PLAYER_HEALED = True

        elif action == 'down':
            if Y < 7 and not (BOSSX == X and BOSSY == Y + 1):
                Y += 1
                if BOARD[Y][X] == 2:
                    PLAYER_HEALED = True

        elif action == 'left':
            if X > 0 and not (BOSSX == X - 1 and BOSSY == Y):
                X -= 1
                if BOARD[Y][X] == 2:
                    PLAYER_HEALED = True

        elif action == 'right':
            if X < 7 and not (BOSSX == X + 1 and BOSSY == Y):
                X += 1
                if BOARD[Y][X] == 2:
                    PLAYER_HEALED = True

        elif action == 'heal':
            if (X == BOSSX and Y == BOSSY - 1) or (X == BOSSX and Y == BOSSY + 1) \
                    or (X == BOSSX - 1 and Y == BOSSY) or (X == BOSSX + 1 and Y == BOSSY):
                HEAL = True

        # BOSS MOVEMENT
        BOSS_MOVEMENT = 'NONE'

        if Y < BOSSY and X < BOSSX:
            if abs(Y - BOSSY) < abs(X - BOSSX):
                BOSS_MOVEMENT = 'RIGHT'
            else:
                BOSS_MOVEMENT = 'DOWN'
        elif Y > BOSSY and X > BOSSX:
            if abs(Y - BOSSY) < abs(X - BOSSX):
                BOSS_MOVEMENT = 'LEFT'
            else:
                BOSS_MOVEMENT = 'UP'

        elif Y > BOSSY and X < BOSSX:
            if abs(Y - BOSSY) < abs(X - BOSSX):
                BOSS_MOVEMENT = 'RIGHT'
            else:
                BOSS_MOVEMENT = 'UP'
        elif Y < BOSSY and X > BOSSX:
            if abs(Y - BOSSY) < abs(X - BOSSX):
                BOSS_MOVEMENT = 'LEFT'
            else:
                BOSS_MOVEMENT = 'DOWN'

        elif BOSSX == X and Y > BOSSY:
            BOSS_MOVEMENT = 'UP'
        elif BOSSX == X and Y < BOSSY:
            BOSS_MOVEMENT = 'DOWN'
        elif BOSSY == Y and X < BOSSX:
            BOSS_MOVEMENT = 'RIGHT'
        elif BOSSY == Y and X > BOSSX:
            BOSS_MOVEMENT = 'LEFT'

        if BOSS_MOVEMENT == 'UP':
            BOSSY -= 1
            if BOARD[BOSSY][BOSSX] == 2:
                DRAGON_HEALED = True

        elif BOSS_MOVEMENT == 'DOWN':
            BOSSY += 1
            if BOARD[BOSSY][BOSSX] == 2:
                DRAGON_HEALED = True

        elif BOSS_MOVEMENT == 'LEFT':
            BOSSX -= 1
            if BOARD[BOSSY][BOSSX] == 2:
                DRAGON_HEALED = True

        elif BOSS_MOVEMENT == 'RIGHT':
            BOSSX += 1
            if BOARD[BOSSY][BOSSX] == 2:
                DRAGON_HEALED = True

        OUTCOMES[action] = (DRAGON_HEALED, PLAYER_HEALED, HEAL)

    return OUTCOMES


# noinspection PyTypeChecker
def process_board(BOARD):
    X, Y = 0, 0
    CATX, CATY = 0, 0
    DOGX, DOGY = 0, 0
    DRAGONX, DRAGONY = 0, 0
    BOSSX, BOSSY = 0, 0

    HP = 200
    MODE = 1

    SPLIT_MAP = BOARD.split(":")
    SPLIT_MAP = [title for title in SPLIT_MAP if title in (
        'yellow_square', 'green_square', 'red_square', 'blue_square', 'D15_DRAGON', 'cat', 'dog', 'dragon', 'D15_SWORD'
        , 'D15_ARMOR', 'ULTRAOMEGAarmor', 'TIMEdragon', 'dogpet', 'catpet', 'dragonpet', 'ULTRAOMEGAsword',
        'GODLYsword')]
    SPLIT_MAP = [SPLIT_MAP[x:x + 8] for x in range(0, len(SPLIT_MAP), 8)]

    BOARD = [[0 for i in range(0, 8)] for i in range(0, 8)]

    for i, line in enumerate(SPLIT_MAP):
        for j, title in enumerate(line):
            if title == 'yellow_square':
                BOARD[i][j] = 'YELLOW'
            elif title == 'green_square':
                BOARD[i][j] = 'GREEN'
            elif title == 'red_square':
                BOARD[i][j] = 'RED'
            elif title == 'blue_square':
                BOARD[i][j] = 'BLUE'

            elif title in ('D15_DRAGON', 'TIMEdragon'):
                BOARD[i][j] = 'NONE'
                BOSSY = i
                BOSSX = j

            elif title in ('D15_SWORD', 'ULTRAOMEGAsword', 'D15_ARMOR', 'ULTRAOMEGAarmor', 'GODLYsword'):
                if title in ('D15_SWORD', 'ULTRAOMEGAsword', 'GODLYsword'):
                    MODE = 1
                else:
                    MODE = 0

                BOARD[i][j] = 'NONE'
                Y = i
                X = j
            elif title in ('cat', 'catpet'):
                BOARD[i][j] = 'NONE'
                CATY = i
                CATX = j
            elif title in ('dog', 'dogpet'):
                BOARD[i][j] = 'NONE'
                DOGY = i
                DOGX = j
            elif title in ('dragon', 'dragonpet'):
                BOARD[i][j] = 'NONE'
                DRAGONY = i
                DRAGONX = j

    for i, line in enumerate(BOARD):
        if 'YELLOW' in line and 'GREEN' in line:
            BOARD[i] = ['YELLOW', 'GREEN', 'YELLOW', 'GREEN', 'YELLOW', 'GREEN', 'YELLOW', 'GREEN']

        elif 'RED' in line and 'BLUE' in line:
            BOARD[i] = ['RED', 'BLUE', 'RED', 'BLUE', 'RED', 'BLUE', 'RED', 'BLUE']

        elif 'GREEN' in line and 'RED' in line:
            BOARD[i] = ['GREEN', 'RED', 'GREEN', 'RED', 'GREEN', 'RED', 'GREEN', 'RED']

        elif 'BLUE' in line and 'YELLOW' in line:
            BOARD[i] = ['BLUE', 'YELLOW', 'BLUE', 'YELLOW', 'BLUE', 'YELLOW', 'BLUE', 'YELLOW']

    return X, Y, CATX, CATY, DOGX, DOGY, DRAGONX, DRAGONY, BOSSX, BOSSY, BOARD, MODE


def process_D15_2_move(map, coolness, dizzyness):
    X, Y, BOSSX, BOSSY = 0, 0, 0, 0
    BOARD = [[0 for i in range(0, 8)] for i in range(0, 8)]
    SPLIT_MAP = map.split(":")
    SPLIT_MAP = [title for title in SPLIT_MAP if title in (
        'purple_square', 'red_circle', 'black_circle', 'D152_DRAGON', 'D152_SWORD', 'TIMEdragonphase2', 'GODLYsword')]
    SPLIT_MAP = [SPLIT_MAP[x:x + 8] for x in range(0, len(SPLIT_MAP), 8)]

    # 0 - PURPLE. 1 - BLACK DOT, 2 - RED DOT
    for i, line in enumerate(BOARD):
        for j, title in enumerate(line):
            if SPLIT_MAP[i][j] == 'purple_square':
                BOARD[i][j] = 0
            elif SPLIT_MAP[i][j] == 'red_circle':
                BOARD[i][j] = 2
            elif SPLIT_MAP[i][j] == 'black_circle':
                BOARD[i][j] = 1
            elif SPLIT_MAP[i][j] in ('D152_DRAGON', 'TIMEdragonphase2'):
                BOARD[i][j] = 1
                BOSSY = i
                BOSSX = j
            elif SPLIT_MAP[i][j] in ('D152_SWORD', 'GODLYsword'):
                BOARD[i][j] = 1
                Y = i
                X = j

    # Dizziness = turns where the dragon won't do anything, EX: dizzy - 1, dragon can be healed, but will move after

    MOVE = ''
    if dizzyness > 0:
        DISTANCE_X = abs(BOSSX - X)
        if DISTANCE_X == 1:
            DISTANCE_X = 0
        DISTANCE_Y = abs(BOSSY - Y)
        if DISTANCE_Y == 1:
            DISTANCE_Y = 0

        POSSIBLE = []
        if DISTANCE_Y + DISTANCE_X <= dizzyness:
            if abs(BOSSY - Y) - 1 < abs(BOSSY - Y) and BOSSY < Y:
                POSSIBLE.append('up')
            if abs(BOSSY - Y) - 1 < abs(BOSSY - Y) and BOSSY > Y:
                POSSIBLE.append('down')
            if abs(BOSSX - X) - 1 < abs(BOSSX - X) and BOSSX < X:
                POSSIBLE.append('left')
            if abs(BOSSX - X) - 1 < abs(BOSSX - X) and BOSSX > X:
                POSSIBLE.append('right')

            outcomes = run_simulation((X, Y, BOSSX, BOSSY), BOARD)

            if 'heal' in outcomes:
                MOVE += 'HEAL'

            if not MOVE:
                for action in POSSIBLE:
                    if action in outcomes:
                        if outcomes[action][1]:
                            MOVE += action.upper()
                            break

            if not MOVE and POSSIBLE:
                MOVE += random.choice(POSSIBLE).upper()

    # 0 - DRAGON_HEALED, 1 - PLAYER_HEALED, 2 - HEAL)
    outcomes = run_simulation((X, Y, BOSSX, BOSSY), BOARD)

    POSSIBLE = []
    if 'heal' in outcomes and not MOVE:
        MOVE += 'HEAL'

    # Check to see id you can avoid healing the dragon adn heal yourself
    if not MOVE:
        POSSIBLE = []
        for action in outcomes:
            if not outcomes[action][0] and outcomes[action][1]:
                POSSIBLE.append(action)

        for action in POSSIBLE:
            if action == 'up':
                if Y >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'UP'
                    break
            elif action == 'down':
                if Y <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'DOWN'
                    break
            elif action == 'left':
                if X >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'LEFT'
                    break
            elif action == 'right':
                if X <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'RIGHT'
                    break

    # Check if you can at least avoid healing the dragon
    if not MOVE:
        POSSIBLE = []
        for action in outcomes:
            if not outcomes[action][0]:
                POSSIBLE.append(action)

        for action in POSSIBLE:
            if action == 'up':
                if Y >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'UP'
                    break
            elif action == 'down':
                if Y <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'DOWN'
                    break
            if action == 'left':
                if X >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'LEFT'
                    break
            elif action == 'right':
                if X <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'RIGHT'
                    break

    # If the dragon will heal anyways, check if at least you can heal too
    if not MOVE:
        for action in outcomes:
            if outcomes[action][1]:
                POSSIBLE.append(action)

        for action in POSSIBLE:
            if action == 'up':
                if Y >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'UP'
                    break
            elif action == 'down':
                if Y <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'DOWN'
                    break
            elif action == 'left':
                if X >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'LEFT'
                    break
            elif action == 'right':
                if X <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'RIGHT'
                    break

    # Just go towards the center since nothing ca be done
    if not MOVE:
        POSSIBLE = ['left', 'right', 'up', 'down']
        for action in POSSIBLE:
            if action == 'up':
                if Y >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'UP'
                    break
            elif action == 'down':
                if Y <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'DOWN'
                    break
            elif action == 'left':
                if X >= 4 or len(POSSIBLE) == 1:
                    MOVE += 'LEFT'
                    break
            elif action == 'right':
                if X <= 3 or len(POSSIBLE) == 1:
                    MOVE += 'RIGHT'
                    break

    return MOVE
    # for outcome in outcomes:
    #     print(outcome, outcomes[outcome])
    # print("===============================")



class D15Data:
    def __init__(self, channel, current_index, solution, asking_msg, last_board, last_hp):
        self.channel       = channel
        self.current_index = current_index
        self.solution      = solution
        self.asking_msg    = asking_msg
        self.last_board    = last_board
        self.last_hp       = last_hp


class D15_2_Data:
    def __init__(self, channel, dizziness, coolness, start_time, message, turn_number):
        self.channel: discord.TextChannel = channel
        self.message: discord.Message = message
        self.dizziness: int = dizziness
        self.coolness: list = coolness
        self.start_time = start_time
        self.turn_number = turn_number


@dataclass
class D10_data:
    def __init__(self, message):
        self.attacker_moves: list = ['CHARGE EDGY SWORD'] * 19 + ['ATTACK']
        self.defender_moves: list = ['WEAKNESS SPELL', 'PROTECT', 'PROTECT', 'PROTECT', 'CHARGE EDGY ARMOR',
                                     'CHARGE EDGY ARMOR',
                                     'PROTECT', 'INVULNERABILITY', 'HEALING SPELL', 'PROTECT', 'PROTECT', 'PROTECT',
                                     'PROTECT', 'PROTECT',
                                     'PROTECT', 'PROTECT']
        self.message: discord.Message = message


def is_d10_embed(author_id, embed_dict):
    try:
        if author_id not in (EPIC_RPG_ID, BETA_BOT_ID):
            return False
        author_match = 'author' in embed_dict and ' — dungeon' in embed_dict['author']['name']
        title_match = 'title' in embed_dict and 'YOU HAVE ENCOUNTERED THE EDGY DRAGON' in embed_dict['title']
        fields_match = 'fields' in embed_dict and any(
            'EDGYdragon' in field['name'] or 'D10_DRAGON' in field['name'] for field in embed_dict['fields']
        )
        return (author_match or title_match) and fields_match
    except Exception:
        log_unmatched_embed(embed_dict)
        return False


def is_d15_2_embed(author_id, embed):
    return author_id in (EPIC_RPG_ID, BETA_BOT_ID) \
        and ('author' in embed and " — dungeon" in embed['author']['name']) \
        and ('fields' in embed and ('THE TIME DRAGON | turn' in embed['fields'][0]['name']
                                    or '<:TIMEdragonphase2:787450872594563082>THE TIME DRAGON' in embed['fields'][0][
                                        'name']))

def is_d13_embed(author_id, embed_dict, force=False):
    try:
        if not force and author_id not in (settings.EPIC_RPG_ID, settings.BETA_BOT_ID, settings.BOT_ID):
            print(f"[D13 SKIP] Author ID {author_id} not recognized")
            return False

        # Check for author and title pattern
        author_name = embed_dict.get('author', {}).get('name', '').lower()
        title_text = embed_dict.get('title', '').lower()

        author_match = ' — dungeon' in author_name
        title_match = 'ultra-omega dragon' in title_text or 'you have encountered the ultra-omega dragon' in title_text

        # Check for field clues
        value_match = False
        for field in embed_dict.get('fields', []):
            field_name = field.get('name', '').lower()
            field_value = field.get('value', '').lower()

            if 'question:' in field_name or 'combat log' in field_name:
                value_match = True
                break
            if 'will move you 1 room closer' in field_value or 'is in the same room as you' in field_value:
                value_match = True
                break

        return (author_match or title_match) and value_match

    except Exception as e:
        print(f"[D13 ERROR] {e}")
        return False


def is_d14_embed(embed_dict):
    title = embed_dict.get("title", "")
    author = (embed_dict.get("author") or {}).get("name", "")
    fields = embed_dict.get("fields", [])

    # 1. Recognize the starting D14 embed (unique title)
    if title.startswith("YOU HAVE ENCOUNTERED THE GODLY DRAGON"):
        return 2

    # 2. Post-move: Author contains ' — dungeon' and at least one field mentions GODLYdragon (field name or value)
    if ' — dungeon' in author:
        for field in fields:
            name = field.get("name", "")
            value = field.get("value", "")
            if "GODLYdragon" in name or "GODLYdragon" in value:
                return 1

    # 3. Not D14 if it didn’t match above
    return 0


def is_d15_embed(author_id: int, embed_dict: dict) -> bool:
    # Only EPIC RPG / Beta Bot posts count
    if author_id not in (EPIC_RPG_ID, BETA_BOT_ID):
        return False

    # Exclude D15.2: look for PHASE 2 or unique emoji/field names
    for field in embed_dict.get('fields', []):
        name = field.get('name', '').upper()
        # Exclude if field name shows D15.2 phase 2
        if "PHASE 2" in name or "DRAGONPHASE2" in name or "TIME DRAGON" in name and "PHASE2" in name:
            return False
        # Exclude the phase2 emoji specifically (if present)
        if "<:TIMEDRAGONPHASE2:" in field.get('name', ''):
            return False

    # Standard D15 checks
    if 'title' in embed_dict and 'THE TIME DRAGON' in embed_dict['title'].upper():
        # Defensive: skip phase 2 if ever in title
        if "PHASE 2" in embed_dict['title'].upper():
            return False
        return True

    for field in embed_dict.get('fields', []):
        name = field.get('name', '').upper()
        if 'TIMEDRAGON' in name or 'D15_DRAGON' in name:
            if "PHASE 2" in name or "DRAGONPHASE2" in name:
                return False
            return True

    return False
