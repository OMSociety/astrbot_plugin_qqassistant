"""HistoryStore / MessageRecord / SessionState 测试（基于真实 API）"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unified_context.history_store import (
    HistoryStore,
    MessageRecord,
    SessionState,
)

# ═══════════════════════════════════════════════
# MessageRecord
# ═══════════════════════════════════════════════


class TestMessageRecord:
    def test_minimal_creation(self):
        msg = MessageRecord(
            msg_id="abc123",
            sender_id="10001",
            sender_name="测试用户",
            content="你好",
            timestamp=1714200000.0,
        )
        assert msg.msg_id == "abc123"
        assert msg.content == "你好"
        assert msg.is_bot is False

    def test_bot_message(self):
        msg = MessageRecord(
            msg_id="bot001",
            sender_id="99999",
            sender_name="Bot",
            content="收到~",
            timestamp=1714200001.0,
            is_bot=True,
        )
        assert msg.is_bot is True

    def test_at_targets(self):
        msg = MessageRecord(
            msg_id="at001",
            sender_id="10001",
            sender_name="A",
            content="@B 你好",
            timestamp=1714200000.0,
            at_targets=[("10002", "B"), ("10003", "C")],
        )
        assert len(msg.at_targets) == 2

    def test_reply_link(self):
        msg = MessageRecord(
            msg_id="reply001",
            sender_id="10002",
            sender_name="B",
            content="嗯嗯",
            timestamp=1714200002.0,
            reply_to_id="abc123",
        )
        assert msg.reply_to_id == "abc123"

    def test_talking_to_group(self):
        msg = MessageRecord(
            msg_id="g001",
            sender_id="10001",
            sender_name="用户",
            content="群聊消息",
            timestamp=1714200000.0,
            talking_to="group",
            talking_to_name="测试群",
        )
        assert msg.talking_to == "group"

    def test_private_chat_talking_to(self):
        msg = MessageRecord(
            msg_id="p001",
            sender_id="10001",
            sender_name="用户",
            content="私聊消息",
            timestamp=1714200000.0,
            talking_to="private",
            talking_to_name="私聊",
        )
        assert msg.talking_to == "private"


# ═══════════════════════════════════════════════
# SessionState
# ═══════════════════════════════════════════════


class TestSessionState:
    def test_default_empty(self):
        state = SessionState()
        assert len(state.messages) == 0
        assert state.bot_last_spoke_at == 0.0
        assert state.bot_last_content == ""

    def test_add_message_respects_maxlen(self):
        state = SessionState()
        state.messages = __import__("collections").deque(maxlen=50)
        for i in range(60):
            state.messages.append(
                MessageRecord(
                    msg_id=f"msg{i}",
                    sender_id="10001",
                    sender_name="用户",
                    content=f"消息{i}",
                    timestamp=1714200000.0 + i,
                )
            )
        assert len(state.messages) == 50
        assert state.messages[0].msg_id == "msg10"

    def test_bot_state_tracking(self):
        state = SessionState()
        state.bot_last_spoke_at = 1714200100.0
        state.bot_last_content = "收到！"
        assert state.bot_last_spoke_at == 1714200100.0
        assert state.bot_last_content == "收到！"


# ═══════════════════════════════════════════════
# HistoryStore（同步 + 异步操作）
# ═══════════════════════════════════════════════


def make_msg(msg_id: str, content: str, is_bot: bool = False, **kw) -> MessageRecord:
    return MessageRecord(
        msg_id=msg_id,
        sender_id="10001",
        sender_name="A",
        content=content,
        timestamp=1714200000.0,
        is_bot=is_bot,
        **kw,
    )


class TestHistoryStore:
    @pytest.fixture
    def store(self):
        return HistoryStore()

    @pytest.mark.asyncio
    async def test_add_and_has_session(self, store):
        await store.add_message("group_123", make_msg("m1", "Hi"))
        assert store.has_session("group_123")

    @pytest.mark.asyncio
    async def test_get_recent(self, store):
        for i in range(5):
            await store.add_message("group_001", make_msg(f"msg{i}", f"内容{i}"))
        recent = store.get_recent("group_001", count=3)
        assert len(recent) == 3
        assert recent[-1].content == "内容4"

    def test_has_session_nonexistent(self, store):
        assert store.has_session("no_such_session") is False

    def test_get_recent_nonexistent(self, store):
        assert store.get_recent("ghost", 5) == []

    @pytest.mark.asyncio
    async def test_get_snapshot(self, store):
        await store.add_message("g", make_msg("m1", "Hello"))
        msgs, state = await store.get_snapshot("g")
        assert len(msgs) == 1
        assert msgs[0].content == "Hello"
        assert isinstance(state, SessionState)

    @pytest.mark.asyncio
    async def test_get_snapshot_nonexistent(self, store):
        msgs, state = await store.get_snapshot("ghost")
        assert msgs == []
        assert isinstance(state, SessionState)

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self, store):
        await store.add_message("g1", make_msg("a1", "g1消息"))
        await store.add_message("g2", make_msg("b1", "g2消息"))
        msgs1, _ = await store.get_snapshot("g1")
        msgs2, _ = await store.get_snapshot("g2")
        assert msgs1[0].content == "g1消息"
        assert msgs2[0].content == "g2消息"
        assert len(msgs1) == 1
        assert len(msgs2) == 1

    @pytest.mark.asyncio
    async def test_record_bot_response(self, store):
        await store.add_message("g", make_msg("u1", "你好"))
        await store.record_bot_response(
            "g",
            content="来了~",
            ts=1714200100.0,
            replied_to="u1",
            replied_to_name="A",
        )
        _, state = await store.get_snapshot("g")
        assert state.bot_last_spoke_at == 1714200100.0
        assert state.bot_last_content == "来了~"
        assert state.bot_last_replied_to == "u1"

    @pytest.mark.asyncio
    async def test_record_bot_response_nonexistent(self, store):
        """不存在的 session 应静默忽略"""
        await store.record_bot_response("ghost", content="test", ts=0.0)

    @pytest.mark.asyncio
    async def test_remove_message_by_id(self, store):
        await store.add_message("g", make_msg("m1", "Hello"))
        await store.add_message("g", make_msg("m2", "World"))
        assert await store.remove_message_by_id("g", "m1") is True
        msgs, _ = await store.get_snapshot("g")
        assert len(msgs) == 1
        assert msgs[0].msg_id == "m2"

    @pytest.mark.asyncio
    async def test_remove_message_by_id_not_found(self, store):
        await store.add_message("g", make_msg("m1", "Hello"))
        assert await store.remove_message_by_id("g", "m99") is False
        assert await store.remove_message_by_id("ghost", "m1") is False

    @pytest.mark.asyncio
    async def test_remove_last_bot_message(self, store):
        await store.add_message("g", make_msg("u1", "用户消息"))
        await store.add_message("g", make_msg("b1", "bot回复", is_bot=True))
        await store.add_message("g", make_msg("u2", "用户又说"))
        assert await store.remove_last_bot_message("g") is True
        msgs, _ = await store.get_snapshot("g")
        assert len(msgs) == 2
        # bot 消息应被移除
        assert all(not m.is_bot for m in msgs)

    @pytest.mark.asyncio
    async def test_remove_last_bot_message_no_bot(self, store):
        await store.add_message("g", make_msg("u1", "只有用户"))
        assert await store.remove_last_bot_message("g") is False

    @pytest.mark.asyncio
    async def test_mc_forward_filtered(self, store):
        """MC 转发消息不应被记录"""
        msg = make_msg("mc1", "MC消息")
        msg.is_mc_forward = True
        await store.add_message("g", msg)
        msgs, _ = await store.get_snapshot("g")
        assert len(msgs) == 0

    def test_session_count(self, store):
        assert store.get_session_count() == 0
