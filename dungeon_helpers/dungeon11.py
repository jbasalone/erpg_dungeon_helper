import copy
import random

import discord
import sqlitedict
import settings

d11_solutions = sqlitedict.SqliteDict('./dbs/d11_solutions.sqlite')

MOVE_TO_EMOJI = {'LEFT': '⬅', 'RIGHT': '➡', 'UP': '⬆', 'DOWN': '⬇', 'PASS TURN': '✋', None: '⁉', 'ATTACK': '🗡'}


class D11Data:
    def __init__(self):
        self.message: discord.Message = None
        self.hp = None
        self.turn_number = 1


async def handle_d11_move(embed: discord.Embed,
                          channel: discord.TextChannel,
                          form_message: bool):

    if embed.title and 'YOU HAVE ENCOUNTERED **THE ULTRA-EDGY DRAGON**' in embed.title:
        board_text = embed.fields[0].value
        hp = 0

        if channel.id in settings.DUNGEON11_HELPERS:
            del settings.DUNGEON11_HELPERS[channel.id]

    else:
        board_text = embed.fields[1].value
        hp = int(embed.fields[0].value.split(' — :heart: ')[1].split('\n')[0].split('/')[0].replace(',', ''))

    if channel.id in settings.DUNGEON11_HELPERS:
        data = settings.DUNGEON11_HELPERS[channel.id]
    else:
        data = D11Data()
        settings.DUNGEON11_HELPERS[channel.id] = data

    data.hp = hp

    x, y, board = extract_d11_data(board_text)

    safe_up_near, safe_up_far, safe_right, safe_left = get_safe_zones(board, x, y)

    print(safe_up_near, safe_up_far, safe_right, safe_left)
    print(x, y)
    for line in board:
        print(line)

    move = get_d11_move(board, x, y, data.hp, safe_up_near, safe_up_far, safe_right, safe_left)

    if form_message or not data.message:
        data.message = await channel.send(f"> **{data.turn_number}. {move} {MOVE_TO_EMOJI[move]}**")
    else:
        await data.message.edit(content=f">  **{data.turn_number}. {move} {MOVE_TO_EMOJI[move]} **")

    data.turn_number += 1


def get_d11_move(board, x, y, hp, safe_up_near, safe_up_far, safe_right, safe_left):
    """
    Returns the best move for a d11 configuration
    """

    if x == 7 and y == 0:
        return "ATTACK"

    if x < 5 and y > 4 and safe_up_near and safe_right and board[y - 1][x + 1] == 0:
        return "RIGHT"

    solution_index = ''

    # Get the index of the solution in the database
    # The 3x3 square above the player
    for i in range(y - 3, y):
        for j in range(x - 1, x + 2):
            if i < 0 or j < 0 or j > 7:
                solution_index += "1"
                continue

            solution_index += str(board[i][j])

    if y == 2:
        solution_index = solution_index[3:]
    elif y == 1:
        solution_index = solution_index[6:]

    encoded_possible_moves = d11_solutions[solution_index]
    possible_moves = set()

    if 'L' in encoded_possible_moves:
        possible_moves.add('LEFT')

    if 'R' in encoded_possible_moves:
        possible_moves.add('RIGHT')

    if 'U' in encoded_possible_moves:
        possible_moves.add('UP')

    if 'P' in encoded_possible_moves:
        possible_moves.add('PASS TURN')

    # Different scenarios
    if not safe_up_near and safe_right and board[y - 1][x + 1] == 0:
        print('CUSTOM SCENARIO --> 2')
        possible_moves.add("RIGHT")

    if not safe_up_near and safe_left and board[y - 1][x - 1] == 0:
        print('CUSTOM SCENARIO --> 1')
        possible_moves.add("LEFT")

    if not safe_up_near and safe_up_far and len(possible_moves) == 1 and 'UP' in possible_moves:
        print('CUSTOM SCENARIO --> 3')
        if x < 7 and board[y - 1][x + 1] == 0:
            possible_moves.add('RIGHT')
        elif x > 0 and board[y - 1][x - 1] == 0:
            possible_moves.add('LEFT')

    if not safe_up_near and len(possible_moves) >= 2 and 'UP' in possible_moves:
        possible_moves.discard('UP')

    if x == 7:
        possible_moves.discard('RIGHT')

    if x == 7 and y <= 2:
        possible_moves.add('UP')

    print(possible_moves, encoded_possible_moves, solution_index)

    if x >= 5 and y >= 3:
        priority_list = ['UP', 'RIGHT', 'LEFT', 'PASS TURN']
    else:
        priority_list = ['RIGHT', 'UP', 'LEFT', 'PASS TURN']

    for move in priority_list:
        if move in possible_moves:
            return move


def get_safe_zones(board: list[list[int]], x: int, y: int):
    """
    Looks at the board, and returns what zones are safe on the board (that contain more safe tiles than fire)
    """

    # The 2 tiles right above the player
    if y > 1 and board[y - 1][x] == 0 and board[y - 2][x] == 0:
        safe_up_near = True
    else:
        safe_up_near = False

    # The 2 above the safe_up_near tiles
    if (y > 3 and board[y - 3][x] == 0 and board[y - 4][x] == 0) \
            or (y > 2 and not (y > 3) and board[y - 3][x] == 0):
        safe_up_far = True
    else:
        safe_up_far = False

    # The 2 tiles upper of left of the known zone
    if x >= 2 and y > 3 and (board[y - 2][x - 2] == 0 and board[y - 3][x - 2] == 0):
        safe_left = True
    else:
        safe_left = False

    # The 2 tiles upper of right of the known
    if x <= 5 and y >= 3 and (board[y - 2][x + 2] == 0 and board[y - 3][x + 2] == 0):
        safe_right = True
    else:
        safe_right = False

    return safe_up_near, safe_up_far, safe_right, safe_left


def extract_d11_data(board_text: str):
    """
    Turns the raw d11 map data into the X, Y coordinates and a list of lists with the fire = 1, safe = 0
    """
    x, y = 0, 0
    board = []

    for i, line in enumerate(board_text.split('\n')):
        line = line.replace('<:', ':') \
            .replace(':950424087187058729>', '') \
            .replace(':1086207554394259487>', '')

        tiles = [tile for tile in line.split(':') if tile][:8]

        map_line = []

        for j, tile in enumerate(tiles):
            if tile == 'D11SW' or tile == 'ULTRAEDGYsword':
                x, y = j, i
                map_line.append(0)
            elif tile == 'fire':
                map_line.append(1)
            else:
                map_line.append(0)

        board.append(map_line)

    return x, y, board


def is_d11_embed(embed: discord.Embed, author_id: int):
    """
    Checks if an embed is a dungeon 11
    """
    return (author_id in (settings.EPIC_RPG_ID, settings.UTILITY_NECROBOT_ID, settings.BETA_BOT_ID)

            and ((embed.author.name and ' — dungeon' in embed.author.name)
                 or (embed.title and 'YOU HAVE ENCOUNTERED **THE ULTRA-EDGY DRAGON**' in embed.title))

            and embed.fields
            and ('D11_Dragon' in embed.fields[0].name or 'ULTRAEDGYdragon' in embed.fields[0].name))


def print_d11_board(board_code):
    count = 0
    for letter in board_code:
        if letter == '0':
            print('S', end='')
        else:
            print('F', end='')

        count += 1
        if count % 3 == 0:
            count = 0
            print()

    print('FPF')


def run_d11_simulations(board: list[list[int]], hp: int, x: int, y: int,
                        max_simulation_count: int, max_turns_count: int):
    initial_board = copy.deepcopy(board)
    initial_hp = hp
    turns = 0
    total_simulations = 0
    path = []

    best_path = []
    best_hp = -10000

    while True:
        if total_simulations >= max_simulation_count:
            return best_path, best_hp

        new_line = [random.randint(0, 1) for i in range(0, 8)]

        allowed_moves = ['PASS TURN']

        if x > 0:
            allowed_moves.append('LEFT')
        if x < 7:
            allowed_moves.append('RIGHT')
        if y > 0:
            allowed_moves.append('UP')

        dung_move = random.choice(allowed_moves)

        if dung_move == 'LEFT':
            if (y > 0 and board[y - 1][x - 1] == 1) or (y == 0 and new_line[x - 1] == 1):
                hp -= 100

            x -= 1

        elif dung_move == 'RIGHT':
            if (y > 0 and board[y - 1][x + 1] == 1) or (y == 0 and new_line[x + 1] == 1):
                hp -= 100

            x += 1

        elif dung_move == 'UP':
            if board[y - 1][x] == 1 or (y >= 1 and board[y - 2][x]) == 1 or (y == 1 and new_line[x] == 1):
                hp -= 100

            y -= 1

        elif dung_move == 'DOWN':
            if board[y + 1][x] == 1:
                hp -= 100

            y += 1

        elif dung_move == 'PASS TURN':
            if (y > 0 and board[y - 1][x] == 1) or (y == 0 and new_line[x] == 1):
                hp -= 110
            else:
                hp -= 10

        if hp <= 0 or turns >= max_turns_count:
            total_simulations += 1

            if hp > best_hp:
                best_path = path
                best_hp = hp

            turns = 0
            hp = initial_hp
            board = copy.deepcopy(initial_board)
            path = []
            continue

        path.append(dung_move)

        for i in range(7, 0, -1):
            board[i] = board[i - 1]

        board[0] = new_line

        turns += 1
