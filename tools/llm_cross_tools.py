"""
跨上下文搜索工具
- search_group_history: 搜索当前群聊历史
- search_other_chats: 搜索其他群/私聊的历史
- get_scene_info: 获取当前场景判断结果

注意：SceneEngine 和 HistoryStore 在首次消息到达前可能尚未初始化，
所以采用懒获取模式，从 plugin 实例动态取。
"""
from __future__ import annotations
import json
from typing import Optional, Any
from astrbot.api.event import filter
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.api import logger


class LLMCrossTools:
    """
    跨上下文搜索工具集（懒获取依赖）
    """

    def __init__(self, plugin_instance: Any):
        self._plugin = plugin_instance
        self._scene = None
        self._store = None

    def _ensure_init(self) -> bool:
        """确保依赖已初始化"""
        if self._scene is not None and self._store is not None:
            return True
        scene = getattr(self._plugin, '_scene_engine', None)
        store = getattr(self._plugin, '_history_store', None)
        if scene is None or store is None:
            return False
        self._scene = scene
        self._store = store
        return True

    @filter.llm_tool()
    async def search_group_history(
        self, event: AiocqhttpMessageEvent, keyword: str, count: int = 10
    ) -> str:
        """
        搜索当前群聊的最近历史内容
        
        Args:
            keyword (str): 搜索关键词
            count (int): 返回结果数量，默认10条，最多50条
        
        Returns:
            str: 格式化的搜索结果
        """
        if not self._plugin.cfg.tools.get("tool_group_search", True):
            return "该功能已关闭~"
        if not self._ensure_init():
            return "上下文引擎尚未初始化，请稍后再试。"
        count = max(1, min(count, 50))
        umo = event.unified_msg_origin
        records = self._store.get_recent(umo, 50)
        matched = [
            f"[{'群友' if not r.is_bot else 'Bot'}] {r.sender_name}: {r.content}"
            for r in records
            if keyword.lower() in r.content.lower()
        ][-count:]
        if not matched:
            return f"在当前群聊中未找到包含「{keyword}」的消息。"
        return "【当前群聊搜索结果】\n" + "\n".join(matched)

    @filter.llm_tool()
    async def search_other_chats(
        self, event: AiocqhttpMessageEvent,
        is_group: bool, subject_id: str, keyword: str, length: int = 20,
    ) -> str:
        """
        跨群/私聊搜索聊天历史
        
        Args:
            is_group (bool): 是否为群聊，True表示群聊，False表示私聊
            subject_id (str): 群号或私聊对象ID
            keyword (str): 搜索关键词
            length (int): 返回结果数量，默认20条，最多100条
        
        Returns:
            str: 格式化的搜索结果
        """
        if not self._plugin.cfg.tools.get("tool_group_search", True):
            return "该功能已关闭~"
        if not self._ensure_init():
            return "上下文引擎尚未初始化，请稍后再试。"
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

    @filter.llm_tool()
    async def get_scene_info(self, event: AiocqhttpMessageEvent) -> str:
        """
        获取当前场景判断结果
        
        Returns:
            str: 场景信息，包括触发类型、对话对象、当前消息等
        """
        if not self._plugin.cfg.tools.get("tool_group_search", True):
            return "该功能已关闭~"
        if not self._ensure_init():
            return "上下文引擎尚未初始化，无法判断场景。"
        umo = event.unified_msg_origin
        records = self._store.get_recent(umo, 10)
        if not records:
            return "当前无群聊历史记录，无法判断场景。"
        current = records[-1]
        trigger_type, trigger_desc = self._scene.detect_trigger(event, current)
        self._scene.infer_addressee(current, records)
        lines = [
            f"触发类型: {trigger_type} — {trigger_desc}",
            f"对话对象: {current.talking_to_name}",
            f"当前消息: {current.sender_name}: {current.content[:50]}",
        ]
        if len(records) > 1:
            prev = records[-2]
            lines.append(f"上一条: {prev.sender_name}: {prev.content[:50]}")
        return "\n".join(lines)


# 全局工具实例（懒初始化）
_cross_tools_instance: Optional["LLMCrossTools"] = None


def register_cross_tools(plugin_instance: Any) -> list:
    """
    注册跨上下文工具到插件实例
    
    Args:
        plugin_instance: 插件实例
    
    Returns:
        list: 注册的工具方法列表
    """
    global _cross_tools_instance
    if _cross_tools_instance is None:
        _cross_tools_instance = LLMCrossTools(plugin_instance)
    for name in ["search_group_history", "search_other_chats", "get_scene_info"]:
        setattr(plugin_instance, name, getattr(_cross_tools_instance, name))
    return [
        _cross_tools_instance.search_group_history,
        _cross_tools_instance.search_other_chats,
        _cross_tools_instance.get_scene_info,
    ]
