"""
跨上下文搜索工具

提供LLM可调用的跨上下文搜索工具（FunctionTool方式）：
- search_group_history: 搜索当前群聊历史
- search_other_chats: 搜索其他群/私聊的历史
- get_scene_info: 获取当前场景判断结果
"""

from __future__ import annotations

import json

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot import logger
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext


class CrossToolBase:
    """跨上下文搜索工具基类"""

    def __init__(self, **data):
        super().__init__(**data)
        self._plugin = None

    def inject_plugin(self, plugin):
        self._plugin = plugin

    def _ensure_init(self) -> bool:
        """确保依赖已初始化"""
        if self._plugin is None:
            return False
        scene = getattr(self._plugin, "_scene_engine", None)
        store = getattr(self._plugin, "_history_store", None)
        return scene is not None and store is not None


@dataclass(config={"arbitrary_types_allowed": True})
class SearchGroupHistoryTool(CrossToolBase, FunctionTool[AstrAgentContext]):
    """搜索当前群聊历史"""

    name: str = "search_group_history"
    description: str = "搜索当前群聊的最近历史内容。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词",
                },
                "count": {
                    "type": "number",
                    "description": "返回结果数量，默认10条，最多50条",
                },
            },
            "required": ["keyword"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            if not self._ensure_init():
                return "上下文引擎尚未初始化，请稍后再试。"


            if not self._plugin.cfg.tools.get("tool_group_search", True):
                return "该功能已关闭~"


            keyword = kwargs.get("keyword", "")
            count = kwargs.get("count", 10)
            count = max(1, min(count, 50))

            event = context.context.event
            store = getattr(self._plugin, "_history_store", None)
            umo = event.unified_msg_origin
            records = store.get_recent(umo, 50)

            matched = [
                f"[{'群友' if not r.is_bot else 'Bot'}] {r.sender_name}: {r.content}"
                for r in records
                if keyword.lower() in r.content.lower()
            ][-count:]

            if not matched:
                return f"在当前群聊中未找到包含「{keyword}」的消息。"


            return "【当前群聊搜索结果】\n" + "\n".join(matched)

        except Exception as e:
            logger.error(f"搜索群聊历史失败: {e}")
            return f"搜索失败: {e}"



@dataclass(config={"arbitrary_types_allowed": True})
class SearchOtherChatsTool(CrossToolBase, FunctionTool[AstrAgentContext]):
    """跨群/私聊搜索历史"""

    name: str = "search_other_chats"
    description: str = "跨群/私聊搜索聊天历史。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "is_group": {
                    "type": "boolean",
                    "description": "是否为群聊，True表示群聊，False表示私聊",
                },
                "subject_id": {
                    "type": "string",
                    "description": "群号或私聊对象ID",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词",
                },
                "length": {
                    "type": "number",
                    "description": "返回结果数量，默认20条，最多100条",
                },
            },
            "required": ["is_group", "subject_id", "keyword"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            if not self._ensure_init():
                return "上下文引擎尚未初始化，请稍后再试。"


            if not self._plugin.cfg.tools.get("tool_group_search", True):
                return "该功能已关闭~"


            is_group = kwargs.get("is_group", True)
            subject_id = kwargs.get("subject_id", "")
            keyword = kwargs.get("keyword", "")
            length = kwargs.get("length", 20)
            length = max(1, min(length, 100))

            type_prefix = "GroupMessage" if is_group else "FriendMessage"
            uid = f"default:{type_prefix}:{subject_id}"

            try:
                conv_mgr = self._plugin.context.conversation_manager
                curr_cid = await conv_mgr.get_curr_conversation_id(uid)
                conv = await conv_mgr.get_conversation(uid, curr_cid)
                history = json.loads(conv.history) if conv and conv.history else []
            except Exception as e:
                logger.error(f"[CrossTools] 获取聊天历史失败: {e}")
                return f"获取聊天历史失败: {e}"


            matched = []
            for msg in history:
                if msg.get("role") not in ("user", "assistant"):
                    continue
                texts = [
                    item.get("text", "")
                    for item in (msg.get("content") or [])
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                content = " ".join(texts)
                if keyword.lower() in content.lower():
                    role_cn = "用户" if msg.get("role") == "user" else "Bot"
                    matched.append(f"[{role_cn}]: {content[:120]}")

            recent = matched[-length:]
            if not recent:
                return f"在指定会话中未找到包含「{keyword}」的消息。"


            scope = f"群{subject_id}" if is_group else f"私聊{subject_id}"
            return f"【{scope} 搜索结果】\n" + "\n".join(recent)

        except Exception as e:
            logger.error(f"跨会话搜索失败: {e}")
            return f"搜索失败: {e}"



@dataclass(config={"arbitrary_types_allowed": True})
class GetSceneInfoTool(CrossToolBase, FunctionTool[AstrAgentContext]):
    """获取当前场景信息"""

    name: str = "get_scene_info"
    description: str = "获取当前场景判断结果，包括触发类型、对话对象等。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            if not self._ensure_init():
                return "上下文引擎尚未初始化，无法判断场景。"


            if not self._plugin.cfg.tools.get("tool_group_search", True):
                return "该功能已关闭~"


            event = context.context.event
            store = getattr(self._plugin, "_history_store", None)
            scene = getattr(self._plugin, "_scene_engine", None)

            umo = event.unified_msg_origin
            records = store.get_recent(umo, 10)

            if not records:
                return "当前无群聊历史记录，无法判断场景。"


            current = records[-1]
            trigger_type, trigger_desc = scene.detect_trigger(event, current)
            scene.infer_addressee(current, records)

            lines = [
                f"触发类型: {trigger_type} — {trigger_desc}",
                f"对话对象: {current.talking_to_name}",
                f"当前消息: {current.sender_name}: {current.content[:50]}",
            ]
            if len(records) > 1:
                prev = records[-2]
                lines.append(f"上一条: {prev.sender_name}: {prev.content[:50]}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"获取场景信息失败: {e}")
            return f"获取场景信息失败: {e}"



def register_cross_tools(plugin_instance) -> None:
    """注册跨上下文搜索工具到 AstrBot"""
    tools = [
        SearchGroupHistoryTool(),
        SearchOtherChatsTool(),
        GetSceneInfoTool(),
    ]

    for tool in tools:
        tool.inject_plugin(plugin_instance)

    plugin_instance.context.add_llm_tools(*tools)

    logger.info(f"[QQAdmin] 已注册 {len(tools)} 个跨上下文搜索工具")
