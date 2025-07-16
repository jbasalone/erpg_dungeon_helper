import copy
import random
import re
import discord
import sqlitedict
import settings
import hashlib

d11_solutions = sqlitedict.SqliteDict('./dbs/d11_solutions.sqlite')
MOVE_TO_EMOJI = {'LEFT': '⬅', 'RIGHT': '➡', 'UP': '⬆', 'DOWN': '⬇', 'PASS TURN': '✋', None: '⁉', 'ATTACK': '🗡'}

class D11Data:
    def __init__(self):
        self.message: discord.Message = None
        self.hp = None
        self.turn_number = 1
        self.last_player_pos = None  # (x, y)
        self.last_move = None        # move name
        self.last_board_hash = None  # hash(board)
        self.has_sent_first_move = False

def hash_board(board):
    return hashlib.sha1(str(board).encode('utf-8')).hexdigest()

async def handle_d11_move(embed: discord.Embed, channel: discord.TextChannel, form_message: bool):
    if (
            embed.fields and
            len(embed.fields) > 0 and
            "is dead" in embed.fields[0].value.lower()
    ):
        print("[D11] Victory detected. Cleaning up.")
        if channel.id in settings.DUNGEON11_HELPERS:
            del settings.DUNGEON11_HELPERS[channel.id]
        return

    if embed.title and 'YOU HAVE ENCOUNTERED **THE ULTRA-EDGY DRAGON**' in embed.title:
        print("[D11] Sending initial move (RIGHT) on intro.")
        data = D11Data()
        data.turn_number = 1
        data.has_sent_first_move = True
        board_text = embed.fields[0].value
        x, y, board = extract_d11_data(board_text)
        board_hash = hash_board(board)
        move = "RIGHT"
        content = f"> **{data.turn_number}. {move} {MOVE_TO_EMOJI[move]}**"
        data.message = await channel.send(content)
        data.last_player_pos = (x, y)
        data.last_move = move
        data.last_board_hash = board_hash
        data.turn_number += 1
        settings.DUNGEON11_HELPERS[channel.id] = data
        print(f"[D11] Initial state: turn={data.turn_number}, pos=({x},{y}), move={move}")
        return

    data = settings.DUNGEON11_HELPERS.get(channel.id)
    if not data:
        print("[D11] No helper data found. Recovering with blank state.")
        data = D11Data()
        data.turn_number = 2
        data.has_sent_first_move = False
        settings.DUNGEON11_HELPERS[channel.id] = data

    data.hp = 0
    try:
        for field in embed.fields:
            hp_match = re.search(r"❤️\s*([\d,]+)", field.value)
            if hp_match:
                data.hp = int(hp_match.group(1).replace(',', ''))
                break
    except Exception:
        data.hp = 0

    if len(embed.fields) < 2 or "map" not in embed.fields[1].name.lower():
        print("[D11] No Map field found, skipping.")
        return

    board_text = embed.fields[1].value
    x, y, board = extract_d11_data(board_text)
    board_hash = hash_board(board)
    safe_up_near, safe_up_far, safe_right, safe_left = get_safe_zones(board, x, y)
    move = get_d11_move(board, x, y, data.hp, safe_up_near, safe_up_far, safe_right, safe_left)

    if (
            data.last_player_pos == (x, y) and
            data.last_move == move and
            data.last_board_hash == board_hash
    ) or (data.has_sent_first_move and data.turn_number == 2):
        print("[D11] Deduplication: Skipping extra move after intro or no state change.")
        data.has_sent_first_move = False
        return

    msg_content = f"> **{data.turn_number}. {move} {MOVE_TO_EMOJI[move]}**"
    if form_message:  # LEGACY: always send a new message per move!
        data.message = await channel.send(msg_content)
    else:  # SLASH: edit last move message if possible
        if data.message is not None:
            await data.message.edit(content=msg_content)
        else:
            data.message = await channel.send(msg_content)

    data.turn_number += 1
    data.last_player_pos = (x, y)
    data.last_move = move
    data.last_board_hash = board_hash
    data.has_sent_first_move = False

def make_move_key(x, y, move):
    # Unique key for the move at a given state; could also hash the board, but this is simple
    return f"{x}:{y}:{move}"

def get_d11_move(board, x, y, hp, safe_up_near, safe_up_far, safe_right, safe_left):
    # 1. High HP (aggressive mode): Always go UP if possible, even on fire
    if hp >= 10000:
        if x == 7 and y == 0:
            return "ATTACK"
        if y > 0:
            return "UP"
        if x < 7:
            return "RIGHT"
        if x > 0:
            return "LEFT"
        return "PASS TURN"

    # 2. Standard logic for normal HP
    if x == 7 and y == 0:
        return "ATTACK"

    if x < 5 and y > 4 and safe_up_near and safe_right and board[y - 1][x + 1] == 0:
        return "RIGHT"

    solution_index = ''
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

    # Additional scenario logic
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
    # Checks for safe tiles in various directions
    if y > 1 and board[y - 1][x] == 0 and board[y - 2][x] == 0:
        safe_up_near = True
    else:
        safe_up_near = False
    if (y > 3 and board[y - 3][x] == 0 and board[y - 4][x] == 0) \
            or (y > 2 and not (y > 3) and board[y - 3][x] == 0):
        safe_up_far = True
    else:
        safe_up_far = False
    if x >= 2 and y > 3 and (board[y - 2][x - 2] == 0 and board[y - 3][x - 2] == 0):
        safe_left = True
    else:
        safe_left = False
    if x <= 5 and y >= 3 and (board[y - 2][x + 2] == 0 and board[y - 3][x + 2] == 0):
        safe_right = True
    else:
        safe_right = False
    return safe_up_near, safe_up_far, safe_right, safe_left

def extract_d11_data(board_text: str):
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