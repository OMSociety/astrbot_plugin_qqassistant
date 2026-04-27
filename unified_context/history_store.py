"""
群聊消息统一存储
- 使用 deque + LRU，避免与框架内置 LTM 冲突
- 同时服务场景感知和原始消息注入
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ============================================================================
# 触发类型常量
# ============================================================================
TRIGGER_PRIVATE = "private_chat"
TRIGGER_AT = "at_bot"
TRIGGER_AT_ALL = "at_all"
TRIGGER_REPLY = "reply_to_bot"
TRIGGER_WAKE = "wake_word"
TRIGGER_MENTION = "mention"
TRIGGER_ACTIVE = "active"
TRIGGER_POKE = "poke"
TRIGGER_UNKNOWN = "unknown"


# ============================================================================
# 数据结构
# ============================================================================
@dataclass(slots=True)
class MessageRecord:
    """轻量级消息记录"""

    msg_id: str
    sender_id: str
    sender_name: str
    content: str
    timestamp: float
    is_bot: bool = False
    is_mc_forward: bool = False
    at_bot: bool = False
    at_all: bool = False
    at_targets: list[tuple[str, str]] = field(default_factory=list)  # (qq, name)
    reply_to_id: str | None = None
    talking_to: str = "group"
    talking_to_name: str = "群聊"


@dataclass(slots=True)
class SessionState:
    """会话状态 - 每个群/私聊一个"""

    messages: deque = field(default_factory=lambda: deque(maxlen=50))
    bot_last_spoke_at: float = 0.0
    bot_last_content: str = ""
    bot_last_replied_to: str = ""
    bot_last_replied_to_name: str = ""
    last_user_interaction: dict[str, float] = field(default_factory=dict)


# ============================================================================
# HistoryStore
# ============================================================================
class HistoryStore:
    """
    统一消息存储，替代 context_aware 的 SessionManager 和
    group_context 的 session_chats dict。

    使用 OrderedDict 实现 LRU + asyncio.Lock 并发保护。
    """

    def __init__(self, max_messages: int = 50, max_sessions: int = 100):
        self._sessions: OrderedDict[str, SessionState] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._cache_lock = asyncio.Lock()
        self._max_messages = max(10, max_messages)
        self._max_sessions = max(10, max_sessions)

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        return self._locks.setdefault(session_id, asyncio.Lock())

    async def _get_or_create_session(self, session_id: str) -> SessionState:
        async with self._cache_lock:
            if session_id in self._sessions:
                self._sessions.move_to_end(session_id)
                return self._sessions[session_id]
            while len(self._sessions) >= self._max_sessions:
                evicted = self._sessions.popitem(last=False)
                self._locks.pop(evicted[0], None)
            state = SessionState()
            state.messages = deque(maxlen=self._max_messages)
            self._sessions[session_id] = state
            return state

    async def add_message(self, session_id: str, msg: MessageRecord) -> None:
        async with self._get_lock(session_id):
            state = await self._get_or_create_session(session_id)
            # 过滤掉MC服务器转发消息，不记录到历史
            if getattr(msg, "is_mc_forward", False):
                return
            state.messages.append(msg)
            if not msg.is_bot:
                state.last_user_interaction[msg.sender_id] = msg.timestamp

    async def get_snapshot(
        self, session_id: str
    ) -> tuple[list[MessageRecord], SessionState]:
        async with self._get_lock(session_id):
            if session_id not in self._sessions:
                return [], SessionState()
            state = self._sessions[session_id]
            return list(state.messages), state

    async def record_bot_response(
        self,
        session_id: str,
        content: str,
        ts: float,
        replied_to: str = "",
        replied_to_name: str = "",
    ) -> None:
        async with self._get_lock(session_id):
            if session_id not in self._sessions:
                return
            state = self._sessions[session_id]
            state.bot_last_spoke_at = ts
            state.bot_last_content = content[:100]
            state.bot_last_replied_to = replied_to
            state.bot_last_replied_to_name = replied_to_name

    def get_recent(self, session_id: str, count: int = 10) -> list[MessageRecord]:
        if session_id not in self._sessions:
            return []
        return list(self._sessions[session_id].messages)[-count:]

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def get_session_count(self) -> int:
        return len(self._sessions)

    async def remove_message_by_id(self, session_id: str, msg_id: str) -> bool:
        async with self._get_lock(session_id):
            if session_id not in self._sessions:
                return False
            state = self._sessions[session_id]
            original = len(state.messages)
            state.messages = deque(
                (m for m in state.messages if m.msg_id != msg_id),
                maxlen=state.messages.maxlen,
            )
            return original - len(state.messages) > 0

    async def remove_last_bot_message(self, session_id: str) -> bool:
        async with self._get_lock(session_id):
            if session_id not in self._sessions:
                return False
            state = self._sessions[session_id]
            if not state.messages:
                return False
            msgs = list(state.messages)
            for i in range(len(msgs) - 1, -1, -1):
                if msgs[i].is_bot:
                    del msgs[i]
                    state.messages = deque(msgs, maxlen=state.messages.maxlen)
                    return True
            return False
