"""
提示词构建器
- 统一场景XML + 原始消息文本的注入
- 防止重复注入（带标记）
- 清空 req.prompt 避免框架重复发送
"""
from __future__ import annotations
from astrbot.api.provider import ProviderRequest
from astrbot.core.agent.message import TextPart


SCENE_MARKER = "<!-- unified_scene_v1 -->"


class PromptBuilder:
    """
    统一提示词构建器
    - inject_scene: 注入 XML 场景描述到 extra_user_content_parts
    - build_text_prompt: 构建原始消息文本（---分割）
    - clear_prompt: 清空 req.prompt 防止框架重复注入
    """

    def __init__(self, max_history: int = 10, max_chars: int = 2000):
        self._max_history = max_history
        self._max_chars = max_chars

    def build_text_prompt(self, records: list, separator: str = "\n---\n") -> str:
        """
        构建原始消息文本（group_context 风格）
        用 separator 分割每条消息。
        """
        if not records:
            return ""

        lines = []
        for rec in records[-self._max_history:]:
            sender = "[Bot]" if rec.is_bot else rec.sender_name
            lines.append(f"{sender}: {rec.content}")

        full = separator.join(lines)
        if len(full) > self._max_chars:
            full = full[-self._max_chars:]
        return full

    def inject_scene(self, req: ProviderRequest, scene_xml: str) -> None:
        """
        安全注入场景 XML 到 extra_user_content_parts，防止重复注入。
        """
        if not scene_xml:
            return
        if scene_xml in (req.system_prompt or ""):
            return
        try:
            parts = getattr(req, 'extra_user_content_parts', None)
            if parts is not None and isinstance(parts, list):
                parts.append(TextPart(text=scene_xml))
                return
        except Exception:
            pass
        try:
            req.system_prompt = (req.system_prompt or "") + f"\n\n{SCENE_MARKER}\n{scene_xml}"
        except Exception:
            pass

    def inject_text_prompt(self, req: ProviderRequest, text: str) -> None:
        """
        将原始消息文本追加到 req.prompt。
        注意：group_context 习惯在 on_llm_request(priority=-10000) 时清空 prompt。
        """
        if not text.strip():
            return
        current = (req.prompt or "").strip()
        req.prompt = (current + "\n" + text).strip() if current else text

    def clear_prompt(self, req: ProviderRequest) -> None:
        """清空 req.prompt，防止框架重复注入"""
        req.prompt = ""
