import discord
import asyncio
import re
import settings
import hashlib

D13_HELPERS = {}
D13_MSG_ANSWERED = set()
D13_ATTACK_SENT = {}

import time
D13_RECENT_RESPONDED = {}

D13_QUESTIONS = [
    {
        'question': "Why does the wooden log tiers goes '...epic, super, mega, hyper...' while enchantments are '...mega, epic, hyper...'",
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
    {'question': "How many miliseconds have passed since you started this dungeon?"}
]

D13_WALKTHROUGH = {
    1: [ (1, "not_so_wrong"), (8, "not_so_wrong"), (15, "wrong"), (14, "wrong"), (13, "wrong"),
         (12, "not_so_wrong"), (11, "not_so_wrong"), (10, "not_so_wrong"), (9, "not_so_wrong"),
         (7, "correct"), (6, "correct"), (2, "attack") ],
    2: [ (2, "not_so_wrong"), (9, "not_so_wrong"), (15, "wrong"), (14, "wrong"), (13, "wrong"),
         (12, "not_so_wrong"), (10, "not_so_wrong"), (8, "correct"), (4, "correct"), (2, "attack") ],
    3: [ (3, "not_so_wrong"), (10, "not_so_wrong"), (9, "not_so_wrong"), (15, "wrong"), (14, "wrong"),
         (13, "wrong"), (12, "not_so_wrong"), (11, "not_so_wrong"), (8, "correct"), (4, "correct"), (2, "attack") ]
}
class D13HelperData:
    def __init__(self):
        self.last_step = 1
        self.message = None
        self.turn_number = 1
        self.previous_room_number = 0
        self.previous_dragon_room = 0

def should_respond_to_message(channel_id, message_id):
    now = time.time()
    key = (channel_id, message_id)
    expire = 3  # seconds
    # Remove old keys
    to_del = [k for k,v in D13_RECENT_RESPONDED.items() if now-v > expire]
    for k in to_del:
        del D13_RECENT_RESPONDED[k]
    if key in D13_RECENT_RESPONDED:
        return False
    D13_RECENT_RESPONDED[key] = now
    return True

def normalize(text):
    return re.sub(r"^[*_\s]+|[*_\s]+$", "", str(text).strip().lower())

def get_answer(_type: str, question: str, left, center, right):
    # Numeric answer handling as in your old code
    try:
        if question == "How many miliseconds have passed since you started this dungeon?":
            sorted_answers = sorted([int(left), int(center), int(right)])
            c, nsr, w = sorted_answers[1], sorted_answers[0], sorted_answers[2]
            if _type == "wrong": return str(w)
            elif _type == "not_so_wrong": return str(nsr)
            elif _type == "correct": return str(c)
        elif question == "How many arena cookies do you have right now?":
            sorted_answers = sorted([int(left), int(center), int(right)])
            c, nsr, w = sorted_answers
            if _type == "wrong": return str(w)
            elif _type == "not_so_wrong": return str(nsr)
            elif _type == "correct": return str(c)
        elif question == "What number am i thinking on right now?":
            sorted_answers = sorted([int(left), int(center), int(right)], reverse=True)
            c, nsr, w = sorted_answers
            if _type == "wrong": return str(w)
            elif _type == "not_so_wrong": return str(nsr)
            elif _type == "correct": return str(c)
    except Exception:
        pass

    # Standard answer mapping
    for possibe in D13_QUESTIONS:
        if possibe['question'] == question:
            return possibe[_type][0]
    return ''

def return_move(answer: str, left, center):
    return '⬅ LEFT' if answer == left else '⬆ CENTER' if answer == center else '➡ RIGHT'

async def get_d13_action(data: D13HelperData, room, dragon_room, prev_room, prev_dragon_room, question, left, center, right):
    messed_up_text = ''
    if data.last_step == 2 and dragon_room > prev_dragon_room:
        data.last_step = 1
        messed_up_text = "(starting from step 1 again because you messed up)"
    elif data.last_step == 3 and room > prev_room:
        data.last_step = 1
        messed_up_text = "(starting from step 1 again because you messed up)"
    if data.last_step == 4 and dragon_room > prev_dragon_room:
        data.last_step = 1
        messed_up_text = "(starting from step 1 again because you messed up)"

    # Progression
    if data.last_step == 1 and room >= 15:
        data.last_step = 2
    elif data.last_step == 2 and dragon_room <= 8:
        data.last_step = 3
    elif data.last_step == 3 and room <= 8:
        data.last_step = 4

    # Pick answer type for this phase
    if data.last_step == 1:
        answer = get_answer('not_so_wrong', question, left, center, right)
        return return_move(answer, left, center) + messed_up_text
    elif data.last_step == 2:
        answer = get_answer('wrong', question, left, center, right)
        return return_move(answer, left, center) + messed_up_text
    elif data.last_step == 3:
        answer = get_answer('not_so_wrong', question, left, center, right)
        return return_move(answer, left, center) + messed_up_text
    elif data.last_step == 4:
        answer = get_answer('correct', question, left, center, right)
        return return_move(answer, left, center) + messed_up_text


def parse_d13_embed(embed: discord.Embed):
    fields = embed.fields
    qa_val = fields[0].value
    q_match = re.search(r"__\*\*QUESTION:\*\*__\s*(.*?)\n:door:", qa_val, re.S)
    left_m = re.search(r"\*\*Left:\*\*\s*(.*)", qa_val)
    center_m = re.search(r"\*\*Center:\*\*\s*(.*)", qa_val)
    right_m = re.search(r"\*\*Right:\*\*\s*(.*)", qa_val)
    question = q_match.group(1).strip() if q_match else None
    left = left_m.group(1).strip() if left_m else None
    center = center_m.group(1).strip() if center_m else None
    right = right_m.group(1).strip() if right_m else None
    # Parse room number from stats field:
    stats_val = fields[2].value
    room_m = re.search(r"\*\*ROOM:\*\* `(\d+)`", stats_val)
    room = int(room_m.group(1)) if room_m else None
    return question, left, center, right, room

def move_string(move, left, center, right):
    if move == "left": return f"⬅ LEFT ({left})"
    if move == "center": return f"⬆ CENTER ({center})"
    if move == "right": return f"➡ RIGHT ({right})"
    if move == "attack": return "⚔ ATTACK"
    return "?"

async def handle_d13_message(message, from_new_message=True, bot_answer_message=None, is_slash=None):
    global D13_HELPERS, D13_MSG_ANSWERED, D13_ATTACK_SENT

    answer_key = (message.channel.id, message.id)
    if answer_key in D13_MSG_ANSWERED:
        return
    D13_MSG_ANSWERED.add(answer_key)

    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return

    embed = message.embeds[0]
    if len(embed.fields) < 3:
        return

    # DRAGON PHASE: Only send one attack per message per channel!
    if any("is in the same room as you" in (f.value.lower()) for f in embed.fields):
        if is_d13_dragon_dead(embed):
            return
        last_attack_msg = D13_ATTACK_SENT.get(message.channel.id)
        if last_attack_msg == message.id:
            print(f"[D13] Already sent attack for message {message.id} in channel {message.channel.id}")
            return
        D13_ATTACK_SENT[message.channel.id] = message.id
        data = D13_HELPERS.get(message.channel.id, D13HelperData())
        content = f"> **{data.turn_number}. ⚔ ATTACK**"
        if is_slash and bot_answer_message:
            await bot_answer_message.edit(content=content)
        else:
            await message.channel.send(content)
        # Immediately clean up ALL state for this channel after ATTACK
        D13_HELPERS.pop(message.channel.id, None)
        D13_ATTACK_SENT.pop(message.channel.id, None)
        return

    # Parse embed details
    fields = embed.fields
    qa_val = fields[0].value
    try:
        question = re.search(r"__\*\*QUESTION:\*\*__\s*(.*?)\n:door:", qa_val, re.S).group(1).strip()
        left = re.search(r"\*\*Left:\*\*\s*(.*)", qa_val).group(1).strip()
        center = re.search(r"\*\*Center:\*\*\s*(.*)", qa_val).group(1).strip()
        right = re.search(r"\*\*Right:\*\*\s*(.*)", qa_val).group(1).strip()
    except Exception as e:
        print("[D13] Could not parse answers:", e)
        return

    stats_val = fields[2].value
    room = int(re.search(r"\*\*ROOM:\*\* `(\d+)`", stats_val).group(1))
    dragon_room = int(re.search(r"ULTRA-OMEGA DRAGON\*\* is (\d+) room", stats_val).group(1))

    # Init/recover state
    if message.channel.id not in D13_HELPERS:
        data = D13HelperData()
        data.previous_room_number = room
        data.previous_dragon_room = dragon_room
        D13_HELPERS[message.channel.id] = data
        D13_ATTACK_SENT.pop(message.channel.id, None)
    else:
        data = D13_HELPERS[message.channel.id]

    action = await get_d13_action(
        data, room, dragon_room, data.previous_room_number, data.previous_dragon_room,
        question, left, center, right)

    data.previous_room_number = room
    data.previous_dragon_room = dragon_room

    content = f"> **{data.turn_number}. {action}**"
    if is_slash and bot_answer_message:
        await bot_answer_message.edit(content=content)
    else:
        await message.channel.send(content)
    data.turn_number += 1

D13_MSG_CACHE = {}      # (channel_id, message_id) -> (message, cache_time)
D13_EDIT_DEBOUNCE = {}  # (channel_id, message_id) -> last_processed_time
D13_EMBED_HASHES = {}   # (channel_id, message_id) -> last_embed_hash

def is_d13_embed_msg(message):
    if message.author.id != settings.EPIC_RPG_ID or not message.embeds:
        return False
    embed = message.embeds[0]
    if len(embed.fields) < 3:
        return False
    qa_text = getattr(embed.fields[0], "value", "")
    stats_text = getattr(embed.fields[2], "value", "")
    if "__**QUESTION:**__" in qa_text and "**ROOM:**" in stats_text:
        if "ULTRA-OMEGA DRAGON" in (embed.title or "") or "THE ULTRA-OMEGA DRAGON" in stats_text.upper():
            return True
    return False

def get_embed_hash(embed):
    if not embed:
        return ""
    h = hashlib.sha1()
    h.update((embed.title or "").encode())
    for f in getattr(embed, "fields", []):
        h.update((f.name or "").encode())
        h.update((f.value or "").encode())
    return h.hexdigest()

def is_d13_dragon_dead(embed):
    lower_title = (getattr(embed, "title", "") or "").lower()
    lower_fields = " ".join([
        (getattr(f, "name", "") + " " + getattr(f, "value", ""))
        for f in getattr(embed, "fields", [])
    ]).lower()
    lower_footer = (getattr(embed.footer, "text", "") or "").lower() if getattr(embed, "footer", None) is not None else ""
    dragon_dead_phrases = [
        "has killed the ultra-omega dragon",
        "the ultra-omega dragon is dead",
        "im ded",
        "💜0/lmao",
        "unlocked the next area"
    ]
    test_text = lower_title + " " + lower_fields + " " + lower_footer
    return any(kw in test_text for kw in dragon_dead_phrases)

async def handle_d13_edit(payload, bot, bot_answer_message=None, is_slash=False):
    now = asyncio.get_event_loop().time()
    key = (payload.channel_id, payload.message_id)
    last = D13_EDIT_DEBOUNCE.get(key, 0)
    if now - last < 3.0:
        print(f"[D13 DEBOUNCE] Skipping rapid re-fetch for {payload.message_id}")
        return
    D13_EDIT_DEBOUNCE[key] = now

    cache_item = D13_MSG_CACHE.get(key)
    if cache_item and now - cache_item[1] < 10.0:
        message = cache_item[0]
        print(f"[D13 CACHE] Using cached message for {payload.message_id}")
    else:
        try:
            channel = await bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            D13_MSG_CACHE[key] = (message, now)
        except Exception as e:
            print(f"[D13 FETCH ERROR] {e}")
            return

    embed = message.embeds[0] if message.embeds else None
    embed_hash = get_embed_hash(embed)
    last_hash = D13_EMBED_HASHES.get(key)
    if last_hash == embed_hash:
        print(f"[D13 EDIT] No embed change for {payload.message_id}, skipping.")
        return
    D13_EMBED_HASHES[key] = embed_hash

    await handle_d13_message(message, bot_answer_message=bot_answer_message, is_slash=is_slash)

    # Clean up caches
    expire_after = 60  # seconds
    for k in list(D13_MSG_CACHE):
        if now - D13_MSG_CACHE[k][1] > expire_after:
            del D13_MSG_CACHE[k]
    for k in list(D13_EDIT_DEBOUNCE):
        if now - D13_EDIT_DEBOUNCE[k] > expire_after:
            del D13_EDIT_DEBOUNCE[k]
    for k in list(D13_EMBED_HASHES):
        if now - D13_EDIT_DEBOUNCE.get(k, 0) > expire_after:
            del D13_EMBED_HASHES[k]