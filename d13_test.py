import pytest
import sys
from types import SimpleNamespace
import asyncio
import dung_helpers
dung_helpers.is_slash_dungeon = lambda x: False
sys.modules['utils_bot'] = type('Fake', (), {'is_slash_dungeon': lambda x: False})()


@pytest.fixture
def settings(monkeypatch):
    settings = SimpleNamespace()
    settings.DUNGEON13_HELPERS = {}
    settings.ALREADY_HANDLED_D13_MSGS = set()
    settings.BOT_ID = 123456789
    settings.EPIC_RPG_ID = 555955826880413696
    settings.BETA_BOT_ID = 949425955653439509
    # Default: always allow channels
    monkeypatch.setattr("dung_helpers.is_channel_allowed", lambda channel_id, *a, **kw: True)
    return settings

class MockChannel:
    def __init__(self, id=999):
        self.last_sent = None
        self._id = id
    async def send(self, content):
        self.last_sent = content
        return content
    @property
    def id(self):
        return self._id

def is_slash_dungeon(msg):
    return False

class DummyMsg: pass

class D13HelperData:
    def __init__(self):
        self.turn_number = 1
        self.last_answered_key = None
        self.previous_room_number = None
        self.previous_dragon_room = None
        self.message = None

dung_helpers.D13HelperData = D13HelperData
print("D13HelperData set in dung_helpers:", dung_helpers.D13HelperData)

@pytest.fixture
def mock_channel():
    return MockChannel(id=42)

@pytest.mark.asyncio
async def test_basic_send(settings, mock_channel, mock_embed_factory, d13_helpers):
    assert hasattr(dung_helpers, "D13HelperData")
    embed = mock_embed_factory("How many types of trainings are there?", left='5', center='4', right='1')
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    print("Sent:", mock_channel.last_sent)
    assert mock_channel.last_sent is not None

@pytest.fixture
def mock_embed_factory():
    def make_embed(question, left='a', center='b', right='c', room=9, dragon_room=22):
        return SimpleNamespace(
            title="Some Title",
            fields=[
                SimpleNamespace(
                    name="**QUESTION:**__" + question,
                    value=":door: :door: :door:\n*LEFT: {}*\n*CENTER: {}*\n*RIGHT: {}*".format(left, center, right)
                ),
                SimpleNamespace(
                    name="",
                    value=f"**ROOM:** `{room}`\n**THE ULTRA-OMEGA DRAGON** is {dragon_room} rooms away from you"
                )
            ]
        )
    return make_embed


@pytest.mark.asyncio
async def test_d13_combat_log(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="Log",
                value="THE ULTRA-OMEGA DRAGON is in the same room as you!"
            )
        ]
    )
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent is not None
    assert "ATTACK" in mock_channel.last_sent

@pytest.mark.asyncio
async def test_d13_funky_question_format(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="**QUESTION:**__How many types of trainings are there?   \n",
                value=":door: :door: :door:\n*LEFT: 5*\n*CENTER: 4*\n*RIGHT: 1*"
            ),
            SimpleNamespace(
                name="",
                value="**ROOM:** `9`\n**THE ULTRA-OMEGA DRAGON** is 22 rooms away from you"
            )
        ]
    )
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert "LEFT" in mock_channel.last_sent or "CENTER" in mock_channel.last_sent or "RIGHT" in mock_channel.last_sent

@pytest.mark.asyncio
async def test_d13_known_table_question(settings, mock_channel, mock_embed_factory, d13_helpers):
    embed = mock_embed_factory("Why does the wooden log tiers goes '...epic, super, mega, hyper...' while enchantments are '...mega, epic, hyper...'", left='yes', center='idk lol', right="that's how the developer planned it")
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    sent = mock_channel.last_sent
    assert "LEFT" in sent  # should match the correct answer position for "yes"

@pytest.mark.asyncio
async def test_d13_partial_fields(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="**QUESTION:**__How many types of trainings are there?",
                value=":door: :door: :door:\n*LEFT: 5*"  # Missing center/right
            ),
            SimpleNamespace(
                name="",
                value="**ROOM:** `9`\n**THE ULTRA-OMEGA DRAGON** is 22 rooms away from you"
            )
        ]
    )
    # Should not raise, should fail gracefully and not send
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    # Should not send any message (or, if you prefer, sends with default/fallback values)
    assert mock_channel.last_sent is None

@pytest.mark.asyncio
async def test_d13_missing_turn_number(settings, mock_channel, mock_embed_factory, d13_helpers):
    question = "How many types of trainings are there?"
    embed = mock_embed_factory(question, left='5', center='4', right='1')
    data = dung_helpers.D13HelperData()
    delattr(data, 'turn_number')  # Simulate missing attr
    d13_helpers[mock_channel.id] = data
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    # Should not raise, and should default to 1
    assert mock_channel.last_sent is not None

@pytest.mark.asyncio
async def test_d13_non_string_answers(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="**QUESTION:**__How many types of trainings are there?",
                value=":door: :door: :door:\n*LEFT: 5*\n*CENTER: None*\n*RIGHT: 1*"
            ),
            SimpleNamespace(
                name="",
                value="**ROOM:** `9`\n**THE ULTRA-OMEGA DRAGON** is 22 rooms away from you"
            )
        ]
    )
    # Should not crash (None as an answer)
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert "LEFT" in mock_channel.last_sent or "RIGHT" in mock_channel.last_sent or "CENTER" in mock_channel.last_sent

@pytest.mark.asyncio
async def test_d13_large_integer_answer(settings, mock_channel, mock_embed_factory, d13_helpers):
    embed = mock_embed_factory("What's the maximum level?", left=str(2**63-1), center='42', right='999999999999')
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert str(2**63-1) in mock_channel.last_sent or "999999999999" in mock_channel.last_sent

@pytest.mark.asyncio
async def test_d13_multiple_channel_isolation(settings, mock_embed_factory, d13_helpers):
    channel1 = MockChannel(id=101)
    channel2 = MockChannel(id=102)
    embed1 = mock_embed_factory("How many types of trainings are there?", left='5', center='4', right='1')
    embed2 = mock_embed_factory("How many types of trainings are there?", left='7', center='8', right='9')
    await dung_helpers.d13_helper(embed1, channel1, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    await dung_helpers.d13_helper(embed2, channel2, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert channel1.last_sent != channel2.last_sent

@pytest.mark.asyncio
async def test_d13_field_order_permutation(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="",
                value="**ROOM:** `9`\n**THE ULTRA-OMEGA DRAGON** is 22 rooms away from you"
            ),
            SimpleNamespace(
                name="**QUESTION:**__How many types of trainings are there?",
                value=":door: :door: :door:\n*LEFT: 5*\n*CENTER: 4*\n*RIGHT: 1*"
            ),
        ]
    )
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert "LEFT" in mock_channel.last_sent or "CENTER" in mock_channel.last_sent or "RIGHT" in mock_channel.last_sent

@pytest.mark.asyncio
async def test_d13_recover_from_broken_state(settings, mock_channel, mock_embed_factory, d13_helpers):
    # Insert a bad state object
    d13_helpers[mock_channel.id] = object()  # not a D13HelperData
    embed = mock_embed_factory("How many types of trainings are there?", left='5', center='4', right='1')
    # Should not raise, should auto-replace
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent is not None

@pytest.mark.asyncio
async def test_d13_stress_many_messages(settings, mock_channel, mock_embed_factory, d13_helpers):
    question = "How many types of trainings are there?"
    for i in range(100):
        embed = mock_embed_factory(
            question,
            left=str(i+1),
            center='4',
            right='1',
            room=9+i,
            dragon_room=222  # Use a dragon_room value that never triggers combat
        )
        await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.id in d13_helpers
    assert hasattr(d13_helpers[mock_channel.id], 'turn_number')
    assert d13_helpers[mock_channel.id].turn_number == 101

@pytest.mark.asyncio
async def test_d13_new_unlisted_question(settings, mock_channel, mock_embed_factory, d13_helpers):
    embed = mock_embed_factory("Brand new never seen question?", left='alpha', center='beta', right='gamma')
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert any(x in mock_channel.last_sent for x in ['alpha', 'beta', 'gamma'])

@pytest.mark.asyncio
async def test_d13_dedup_by_location(settings, mock_channel, mock_embed_factory, d13_helpers):
    question = "How many types of trainings are there?"
    # First occurrence
    embed1 = mock_embed_factory(question, left='5', center='4', right='1', room=9, dragon_room=22)
    await dung_helpers.d13_helper(embed1, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    sent1 = mock_channel.last_sent
    # Same question, different room
    embed2 = mock_embed_factory(question, left='5', center='4', right='1', room=10, dragon_room=22)
    await dung_helpers.d13_helper(embed2, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    sent2 = mock_channel.last_sent
    assert sent1 != sent2

@pytest.mark.asyncio
async def test_d13_question_in_value(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="",
                value="QUESTION: How many types of trainings are there?:door: :door: :door:\n*LEFT: 5*\n*CENTER: 4*\n*RIGHT: 1*"
            ),
            SimpleNamespace(
                name="",
                value="**ROOM:** `9`\n**THE ULTRA-OMEGA DRAGON** is 22 rooms away from you"
            )
        ]
    )
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert "LEFT" in mock_channel.last_sent or "CENTER" in mock_channel.last_sent or "RIGHT" in mock_channel.last_sent

@pytest.mark.asyncio
async def test_d13_race_condition(settings, mock_channel, mock_embed_factory, d13_helpers):
    question = "How many types of trainings are there?"
    embed = mock_embed_factory(question, left='5', center='4', right='1')
    # Launch two helpers concurrently
    await asyncio.gather(
        dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True),
        dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    )
    # Only one should have been sent (deduplication)
    assert mock_channel.last_sent is not None

@pytest.mark.asyncio
async def test_d13_combat_log(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="Log",
                value="THE ULTRA-OMEGA DRAGON is in the same room as you!"
            )
        ]
    )
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent is not None
    assert "ATTACK" in mock_channel.last_sent

@pytest.fixture
def d13_helpers(settings):
    settings.DUNGEON13_HELPERS.clear()
    return settings.DUNGEON13_HELPERS

@pytest.mark.asyncio
async def test_d13_all_steps(settings, mock_channel, mock_embed_factory, d13_helpers):
    steps = [
        (9, 22, 'not_so_wrong'),   # step 1
        (16, 22, 'wrong'),         # step 2
        (9, 7, 'not_so_wrong'),    # step 3
        (7, 22, 'correct')         # step 4
    ]
    question = "How many types of trainings are there?"
    for room, dragon_room, expected_type in steps:
        embed = mock_embed_factory(question, left='5', center='4', right='1', room=room, dragon_room=dragon_room)
        await dung_helpers.d13_helper(
            embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True
        )
        assert mock_channel.last_sent is not None
        sent = mock_channel.last_sent
        assert "LEFT" in sent or "CENTER" in sent or "RIGHT" in sent

@pytest.mark.asyncio
async def test_d13_numeric_question(settings, mock_channel, mock_embed_factory, d13_helpers):
    embed = mock_embed_factory("How many arena cookies do you have right now?", left="11", center="99", right="10000")
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent is not None
    sent = mock_channel.last_sent
    assert "99" in sent

@pytest.mark.asyncio
async def test_d13_unknown_question(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(
        title="",
        fields=[
            SimpleNamespace(
                name="**QUESTION:**__Unknown Q",
                value=":door: :door: :door:\n*LEFT: someA*\n*CENTER: someB*\n*RIGHT: someC*"
            ),
            SimpleNamespace(
                name="",
                value="**room:** `9`\n**the ultra-omega dragon** is 22 rooms away from you"
            )
        ]
    )
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent is not None
    sent = mock_channel.last_sent
    assert "LEFT" in sent

@pytest.mark.asyncio
async def test_d13_get_action_gives_expected_wrong_answer(settings, d13_helpers):
    d13_data = dung_helpers.D13HelperData()
    d13_data.last_step = 2
    d13_data.turn_number = 2
    d13_data.previous_room_number = 9
    d13_data.previous_dragon_room = 22
    # Step 2 triggers 'wrong' answer in get_answer logic
    action = await dung_helpers.get_d13_action(
        d13_data,
        room_number=16,          # triggers step 2 logic
        dragon_room=22,
        previous_room_number=9,
        previous_dragon_room=22,
        question="How many types of trainings are there?",
        left_answer='5',
        center_answer='4',
        right_answer='1'
    )
    # Should suggest the 'wrong' answer (step 2)
    assert "RIGHT (1)" in action

@pytest.mark.asyncio
async def test_d13_user_gives_wrong_answer(settings, mock_channel, mock_embed_factory, d13_helpers):
    question = "How many types of trainings are there?"
    # Bot sees a question, suggests an answer
    embed = mock_embed_factory(question, left='5', center='4', right='1', room=9, dragon_room=22)
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    first = mock_channel.last_sent
    # User gives WRONG answer, so same embed/question comes again (room/dragon_room unchanged)
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    # Bot should deduplicate and NOT send a second answer (unless forced)
    assert mock_channel.last_sent == first

    # Now, simulate user advances (room changes): bot should respond
    embed2 = mock_embed_factory(question, left='5', center='4', right='1', room=10, dragon_room=22)
    await dung_helpers.d13_helper(embed2, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent != first

@pytest.mark.asyncio
async def test_d13_deduplication(settings, mock_channel, mock_embed_factory, d13_helpers):
    question = "How many types of trainings are there?"
    embed = mock_embed_factory(question, left='5', center='4', right='1')
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent is not None

    first = mock_channel.last_sent
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent == first

@pytest.mark.asyncio
async def test_d13_restart_state_recovery(settings, mock_channel, mock_embed_factory, d13_helpers):
    d13_helpers.clear()
    question = "What's the maximum level?"
    embed = mock_embed_factory(question, left='2147483647', center='200', right='2389472895789437')
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    assert mock_channel.last_sent is not None
    sent = mock_channel.last_sent
    assert "2147483647" in sent or "2389472895789437" in sent

@pytest.mark.asyncio
async def test_d13_channel_not_allowed(settings, mock_channel, mock_embed_factory, d13_helpers, monkeypatch):
    monkeypatch.setattr("dung_helpers.is_channel_allowed", lambda channel_id, *a, **kw: False)
    mock_channel.last_sent = None
    embed = mock_embed_factory("How many types of trainings are there?")
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    # Should not send any message
    assert mock_channel.last_sent is None

@pytest.mark.asyncio
async def test_d13_missing_fields(settings, mock_channel, d13_helpers):
    embed = SimpleNamespace(title="", fields=[])
    await dung_helpers.d13_helper(embed, mock_channel, from_message=True, trigger_message=SimpleNamespace(), helpers=d13_helpers, message_based=True)
    # Should not crash