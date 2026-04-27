"""
场景感知引擎
- 来自 context_aware 的核心逻辑，精简后移植
- 判断触发类型（@、回复、主动触发等）
- 推断对话对象（谁→谁）
"""

from __future__ import annotations

import re
import time

from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import At, AtAll, Image, Plain, Reply

from .history_store import (
    TRIGGER_ACTIVE,
    TRIGGER_AT,
    TRIGGER_PRIVATE,
    TRIGGER_REPLY,
    TRIGGER_UNKNOWN,
    TRIGGER_WAKE,
    MessageRecord,
)

# 回复特征词
DEFAULT_REPLY_STARTERS = frozenset(
    {
        "好的",
        "好",
        "嗯",
        "是的",
        "对",
        "谢谢",
        "感谢",
        "收到",
        "明白",
        "知道了",
        "了解了",
        "可以",
        "行",
        "没问题",
        "ok",
        "OK",
        "Ok",
        "好滴",
        "好哒",
        "好嘞",
        "okok",
    }
)


class SceneEngine:
    """
    场景感知引擎 - 判断"这条消息是什么场景"

    核心问题：Bot 主动加入对话时，误以为别人在问自己。
    解决方案：通过触发类型 + 对话对象双重判断，决定 LLM 的行为。
    """

    def __init__(self, bot_id: str, bot_names: list[str] | None = None):
        self._bot_id = bot_id
        self._bot_names = [n.lower() for n in (bot_names or [])]

    @property
    def bot_id(self) -> str:
        return self._bot_id

    def extract_message(self, event: AstrMessageEvent) -> MessageRecord:
        """从事件中提取消息记录"""
        from .history_store import MessageRecord

        sender_id = event.get_sender_id()
        parts = []

        for comp in event.get_messages():
            if isinstance(comp, Plain) and comp.text:
                parts.append(comp.text)
            elif isinstance(comp, Image):
                parts.append("[图片]")

        content = "".join(parts) or event.message_str or "[消息]"

        msg = MessageRecord(
            msg_id=str(getattr(event.message_obj, "message_id", "?")),
            sender_id=sender_id,
            sender_name=event.get_sender_name() or sender_id,
            content=content[:500],
            timestamp=time.time(),
            is_bot=(sender_id == self._bot_id),
        )

        # 检测是否为MC服务器转发消息（通过特殊格式判断）
        # 支持格式：
        # - 〔玩家名〕消息 (〔player〕message)
        # - <玩家名> 消息 (<player> message)
        # - [玩家名] 消息 [player] message
        # - [#MC:xxx] 隐藏标记
        mc_patterns = [
            r"^〔[^〕]+〕",  # 〔玩家名〕消息
            r"^<[^>]+>\s",  # <玩家名> 消息
            r"^\[[^\]]+\]\s",  # [玩家名] 消息
            r" #MC:",  # [#MC:xxx] 隐藏标记
        ]
        if any(re.search(p, content) for p in mc_patterns):
            msg.is_mc_forward = True
            # 提取MC玩家名，改写sender信息，使上下文检索能正确识别
            mc_name_match = re.match(r"〔([^〕]+)〕", content) or re.match(r"<([^>]+)>\s", content) or re.match(r"\[([^\]]+)\]\s", content)
            if mc_name_match:
                player_name = mc_name_match.group(1)
                msg.sender_name = player_name
                msg.sender_id = f"mc:{player_name}"
                msg.is_bot = False

        for comp in event.get_messages():
            if isinstance(comp, At):
                qq_str = str(comp.qq)
                msg.at_targets.append((qq_str, getattr(comp, "name", qq_str)))
                if qq_str == self._bot_id:
                    msg.at_bot = True
            elif isinstance(comp, AtAll):
                msg.at_all = True
            elif isinstance(comp, Reply) and comp.sender_id:
                msg.reply_to_id = str(comp.sender_id)
                # 检测被引用消息是否为MC转发，提取游戏ID
                reply_text = getattr(comp, "message_str", "") or ""
                if reply_text:
                    mc_reply_match = re.match(r"〔([^〕]+)〕", reply_text)
                    if mc_reply_match:
                        msg.reply_to_mc_player = mc_reply_match.group(1)

        return msg

    def detect_trigger(
        self, event: AstrMessageEvent, msg: MessageRecord
    ) -> tuple[str, str]:
        """检测触发类型"""
        if msg.is_mc_forward:
            return "ignore", "MC服务器转发消息"

        if event.is_private_chat():
            return TRIGGER_PRIVATE, f"{msg.sender_name} 在私聊中"

        if msg.at_bot:
            return TRIGGER_AT, f"{msg.sender_name} @了你"

        if msg.at_all:
            return "at_all", f"{msg.sender_name} @了全体"

        if msg.reply_to_id == self._bot_id:
            # 注意：MC消息被引用的情况在 infer_addressee 中处理
            # 这里不做特殊处理，保持正常触发
            return TRIGGER_REPLY, f"{msg.sender_name} 在回复你"

        if event.is_at_or_wake_command and not msg.at_bot:
            return TRIGGER_WAKE, f"{msg.sender_name} 使用唤醒词"

        # 检查是否被提及Bot昵称
        if self._bot_names:
            msg_lower = msg.content.lower()
            for name in self._bot_names:
                if name and name in msg_lower:
                    return "mention", f"{msg.sender_name} 提到了你"

        # 主动触发（无明确触发条件但触发了LLM）
        if not event.is_at_or_wake_command and not event.is_private_chat():
            return TRIGGER_ACTIVE, "主动触发，无人明确呼唤"

        return TRIGGER_UNKNOWN, "触发来源未知"

    def infer_addressee(
        self,
        msg: MessageRecord,
        history: list[MessageRecord],
        bot_replied_to: str = "",
        bot_replied_to_name: str = "",
    ) -> str:
        """
        推断对话对象。

        核心原则：宁可信"群聊"，不可激进判断"在和Bot说话"。
        只有高置信度时才判断 talking_to = "bot"。
        """
        if getattr(msg, "is_mc_forward", False):
            return "ignore"

        # 规则1：@Bot
        if msg.at_bot:
            msg.talking_to = "bot"
            msg.talking_to_name = "你"
            return "bot"

        # 规则2：@其他人
        if msg.at_targets and msg.at_targets[0][0] != self._bot_id:
            msg.talking_to = msg.at_targets[0][0]
            msg.talking_to_name = msg.at_targets[0][1]
            return msg.talking_to

        # 规则3：回复某人
        if msg.reply_to_id:
            # MC回复优先：从Reply组件提取的MC玩家名
            if getattr(msg, "reply_to_mc_player", None):
                msg.talking_to = msg.reply_to_mc_player
                msg.talking_to_name = f"MC:{msg.reply_to_mc_player}"
                return msg.reply_to_mc_player

            if msg.reply_to_id == self._bot_id:
                # 检查被回复的消息是否是MC服务器转发消息
                # reply_to_id 是被回复消息的 sender_id，这里检查最近一条bot消息是否是MC转发
                replied_to_is_mc = False
                for m in reversed(history):
                    if m.is_bot:
                        replied_to_is_mc = getattr(m, "is_mc_forward", False)
                        break
                if not replied_to_is_mc:
                    msg.talking_to = "bot"
                    msg.talking_to_name = "你"
                    return "bot"
                # MC转发消息被引用，降级为群聊
            else:
                msg.talking_to = msg.reply_to_id
                for m in reversed(history):
                    if m.sender_id == msg.reply_to_id:
                        msg.talking_to_name = m.sender_name
                        break
                else:
                    msg.talking_to_name = msg.reply_to_id
            return msg.talking_to

        # 规则4：Bot刚回复了此人，此人在回复Bot
        # 但如果Bot上一条是MC服务器转发消息，则不触发此规则
        if history:
            last = history[-1]
            time_gap = msg.timestamp - last.timestamp
            # 检查上一条是否是MC转发消息
            last_is_mc_forward = getattr(last, "is_mc_forward", False)
            if (
                last.is_bot
                and not last_is_mc_forward
                and time_gap < 35
                and bot_replied_to == msg.sender_id
            ):
                stripped = msg.content.strip()
                if (
                    stripped
                    and len(stripped) <= 20
                    and self._looks_like_reply(stripped)
                ):
                    msg.talking_to = "bot"
                    msg.talking_to_name = "你"
                    return "bot"

        return "group"

    def _looks_like_reply(self, content: str) -> bool:
        return any(content.startswith(s) for s in DEFAULT_REPLY_STARTERS)

    def build_scene_xml(
        self,
        trigger_type: str,
        trigger_desc: str,
        current: MessageRecord,
        flow: list[MessageRecord],
        bot_last_spoke_at: float,
    ) -> str:
        """构建 XML 场景描述"""
        import time

        is_talking_to_bot = current.talking_to == "bot"
        is_talking_to_group = current.talking_to == "group"

        instruction_map = {
            TRIGGER_AT: "用户在和你对话，请正常回复。",
            "at_all": "用户@了全体，请正常回复。",
            TRIGGER_REPLY: "用户在回复你，请正常回复。",
            TRIGGER_PRIVATE: "私聊对话，请正常回复。",
            "mention": "用户提到了你，可以适当回复。",
            TRIGGER_ACTIVE: (
                "【注意】你是主动加入对话的。"
                + (
                    "用户可能在回复你，请谨慎判断。"
                    if is_talking_to_bot
                    else "这条消息是说给群里大家的，不要当成在问你。"
                )
                + " 合适做法：1)发表看法 2)补充信息 3)保持沉默。"
            ),
            TRIGGER_UNKNOWN: "【谨慎】触发来源未知，请保持观望。",
        }
        instruction = instruction_map.get(trigger_type, "")

        lines = ["<conversation_scene>"]
        lines.append(f'  <trigger type="{trigger_type}">{trigger_desc}</trigger>')

        # 当前消息
        if is_talking_to_bot:
            to_name = "你（Bot）"
        elif is_talking_to_group:
            to_name = "群里所有人（非特定对象）"
        else:
            to_name = current.talking_to_name

        lines.append("  <current>")
        lines.append(f"    <sender>{self._esc(current.sender_name)}</sender>")
        lines.append(f"    <talking_to>{to_name}</talking_to>")
        lines.append(f"    <content>{self._esc(current.content[:80])}</content>")
        lines.append("  </current>")

        if instruction:
            lines.append(f"  <instruction>{instruction}</instruction>")

        # 最近对话流
        if flow and len(flow) > 1:
            flow_lines = []
            for m in flow[-5:]:
                to = "你" if m.talking_to == "bot" else (m.talking_to_name or "群")
                sender = "[你]" if m.is_bot else m.sender_name
                preview = m.content[:20] + ("..." if len(m.content) > 20 else "")
                flow_lines.append(
                    f"    <m>{self._esc(sender)} → {self._esc(to)}: {self._esc(preview)}</m>"
                )
            lines.append("  <recent_flow>")
            lines.extend(flow_lines)
            lines.append("  </recent_flow>")

        # Bot最近发言状态
        if bot_last_spoke_at > 0:
            mins = (time.time() - bot_last_spoke_at) / 60
            if 0 < mins < 60:
                lines.append(f'  <your_last_message minutes_ago="{mins:.1f}"/>')

        lines.append("</conversation_scene>")
        return "\n".join(lines)

    @staticmethod
    def _esc(text: str) -> str:
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
