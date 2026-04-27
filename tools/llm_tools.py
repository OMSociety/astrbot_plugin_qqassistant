"""
LLM工具模块

提供LLM可调用的QQ群管工具函数（FunctionTool方式）：
- 获取群成员列表
- 获取用户信息
- 获取群信息
- 戳一戳
- 禁言/解禁
- 设置群头衔
- 修改群名片
- 设置精华消息
"""

from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot import logger
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

from ..config import PluginConfig

# ============ Tool 基类 ============


class QQToolBase:
    """QQ工具基类"""

    def __init__(self, **data):
        super().__init__(**data)
        self.cfg: PluginConfig | None = None
        self.bot = None

    def inject_config(self, cfg: PluginConfig):
        """注入配置"""
        self.cfg = cfg

    def _check_enabled(self, tool_key: str) -> tuple[bool, str]:
        """检查工具开关是否启用"""
        if self.cfg and not self.cfg.tools.get(tool_key, True):
            return False, "该功能已关闭~"
        return True, ""

    def _get_bot(self, context: ContextWrapper) -> Any:
        """获取 bot 实例"""
        try:
            return context.context.event.bot
        except Exception:
            return getattr(self, "bot", None)


# ============ Tool 定义 ============


@dataclass(config={"arbitrary_types_allowed": True})
class GetGroupMemberListTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """获取群成员列表工具"""

    name: str = "get_group_member_list"
    description: str = "获取当前群聊成员列表（昵称/名片/QQ/身份/头衔）。重要提示：在调用需要 user_id 的工具（如禁言、设置头衔、戳一戳）前，应先调用本工具获取群成员列表和对应的QQ号码。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_info")
            if not enabled:
                return ToolExecResult(msg)

            event = context.context.event
            group_id = event.get_group_id()
            if not group_id:
                return ToolExecResult("当前是私聊会话，无法获取群成员列表。")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            member_list = await bot.get_group_member_list(
                group_id=int(group_id), no_cache=True
            )
            if not member_list:
                return ToolExecResult("获取群成员列表失败或列表为空。")

            role_map = {"owner": "群主", "admin": "管理员", "member": "成员"}
            members = []
            for m in member_list:
                uid = m.get("user_id")
                nickname = m.get("nickname", "")
                card = m.get("card", "")
                title = m.get("title", "")
                role = role_map.get(m.get("role", "member"), "成员")
                display = card or nickname or str(uid)
                members.append((display, uid, role, title, nickname, card))

            members.sort(key=lambda x: x[0])

            out = [f"当前群成员列表 (共 {len(members)} 人):"]
            for display, uid, role, title, nickname, card in members:
                line = f"[{role}] {display} (QQ: {uid})"
                if title:
                    line += f" [头衔: {title}]"
                if card and nickname and card != nickname:
                    line += f" (原名: {nickname})"
                out.append(line)

            return ToolExecResult("\n".join(out))
        except Exception as e:
            logger.error(f"获取群成员列表失败: {e}")
            return ToolExecResult(f"获取群成员列表失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class GetUserInfoTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """获取用户信息工具"""

    name: str = "get_user_info"
    description: str = "获取QQ用户信息（群聊优先取群成员信息，否则取陌生人信息）。包含QQ号、昵称、群名片、身份、头衔、等级等。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "qq_id": {
                    "type": "string",
                    "description": "要查询的QQ号，默认为空表示查询消息发送者",
                },
            },
            "required": [],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_info")
            if not enabled:
                return ToolExecResult(msg)

            event = context.context.event
            qq_id = kwargs.get("qq_id")
            target_id = str(qq_id) if qq_id else str(event.get_sender_id())

            if not target_id:
                return ToolExecResult("未指定查询对象。")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            group_id = event.get_group_id()
            if group_id:
                info = await bot.get_group_member_info(
                    group_id=int(group_id), user_id=int(target_id), no_cache=True
                )
                role_map = {"owner": "群主", "admin": "管理员", "member": "成员"}
                role_cn = role_map.get(info.get("role", "member"), "成员")

                s = [f"QQ: {target_id}"]
                s.append(f"昵称: {info.get('nickname', '未知')}")
                if info.get("card"):
                    s.append(f"群名片: {info.get('card')}")
                s.append(f"身份: {role_cn}")
                if info.get("title"):
                    s.append(f"头衔: {info.get('title')}")
                if info.get("level") is not None:
                    s.append(f"等级: {info.get('level')}")
                return ToolExecResult("\n".join(s))

            info = await bot.get_stranger_info(user_id=int(target_id), no_cache=True)
            s = [f"QQ: {target_id}", f"昵称: {info.get('nickname', '未知')}"]
            return ToolExecResult("\n".join(s))
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return ToolExecResult(f"获取用户信息失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class GetGroupInfoTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """获取群信息工具"""

    name: str = "get_group_info"
    description: str = "获取当前群的详细信息，包括群号、群名、群人数、群主、描述等。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_info")
            if not enabled:
                return ToolExecResult(msg)

            event = context.context.event
            group_id = event.get_group_id()
            if not group_id:
                return ToolExecResult("当前是私聊会话，无法获取群信息。")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            info = await bot.get_group_info(group_id=int(group_id))
            if not info:
                return ToolExecResult("获取群信息失败。")

            import time

            s = [f"群号: {group_id}"]
            if info.get("group_name"):
                s.append(f"群名: {info.get('group_name')}")
            if info.get("member_count") is not None:
                s.append(f"当前人数: {info.get('member_count')}")
            if info.get("max_member_count") is not None:
                s.append(f"最大人数: {info.get('max_member_count')}")
            if info.get("group_description"):
                s.append(f"群描述: {info.get('group_description')}")
            if info.get("group_create_time"):
                create_time = time.strftime(
                    "%Y-%m-%d", time.localtime(info.get("group_create_time"))
                )
                s.append(f"创建时间: {create_time}")

            return ToolExecResult("\n".join(s))
        except Exception as e:
            logger.error(f"获取群信息失败: {e}")
            return ToolExecResult(f"获取群信息失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class PokeUserTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """戳一戳工具"""

    name: str = "poke_user"
    description: str = "戳一戳指定用户（群聊/私聊自动判断）。重要提示：如果不知道对方的QQ号，请先调用 get_group_member_list 获取群成员列表。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "qq_id": {
                    "type": "string",
                    "description": "要戳的用户的QQ号，必定为数字字符串，如 '12345678'",
                },
            },
            "required": ["qq_id"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_action")
            if not enabled:
                return ToolExecResult(msg)

            qq_id = kwargs.get("qq_id", "")
            if not qq_id:
                return ToolExecResult("请提供要戳的用户QQ号")

            event = context.context.event
            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            group_id = event.get_group_id()
            if group_id:
                await bot.group_poke(group_id=int(group_id), user_id=int(qq_id))
            else:
                await bot.friend_poke(user_id=int(qq_id))

            logger.info(f"戳一戳用户 {qq_id} 成功")
            return ToolExecResult(f"已戳一戳用户 {qq_id}。")
        except Exception as e:
            logger.error(f"戳一戳失败: {e}")
            return ToolExecResult(f"戳一戳失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class SetGroupBanTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """禁言工具"""

    name: str = "set_group_ban"
    description: str = "对个人进行禁言（带简单权限判定提示）。重要提示：如果不知道对方的QQ号，请先调用 get_group_member_list 获取群成员列表。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "要禁言的用户的QQ号，必定为数字字符串，如 '12345678'",
                },
                "duration": {
                    "type": "number",
                    "description": "禁言持续时间（秒），范围为0~86400, 0表示取消禁言",
                },
            },
            "required": ["user_id", "duration"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_action")
            if not enabled:
                return ToolExecResult(msg)

            user_id = kwargs.get("user_id", "")
            duration = kwargs.get("duration", 60)

            if not user_id:
                return ToolExecResult("请提供要禁言的用户QQ号")

            event = context.context.event
            group_id = event.get_group_id()
            if not group_id:
                return ToolExecResult("仅在群聊中才可以禁言。")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            role_map = {"owner": "群主", "admin": "管理员", "member": "成员"}
            try:
                login = await bot.get_login_info()
                bot_id = str(login.get("user_id"))
                bot_info = await bot.get_group_member_info(
                    group_id=int(group_id), user_id=int(bot_id), no_cache=True
                )
                tgt_info = await bot.get_group_member_info(
                    group_id=int(group_id), user_id=int(user_id), no_cache=True
                )
                bot_role = bot_info.get("role", "member")
                tgt_role = tgt_info.get("role", "member")

                if bot_role == "admin" and tgt_role != "member":
                    return ToolExecResult(
                        f"禁言失败：权限不足。你的身份：{role_map.get(bot_role)}，对方的身份：{role_map.get(tgt_role)}"
                    )
                if bot_role == "member":
                    return ToolExecResult("禁言失败：机器人不是管理员/群主。")
                if bot_role == "owner" and tgt_role == "owner":
                    return ToolExecResult("禁言失败：不能对群主禁言。")
            except Exception:
                pass

            await bot.set_group_ban(
                group_id=int(group_id), user_id=int(user_id), duration=int(duration)
            )
            action = "解除禁言" if int(duration) == 0 else f"禁言 {duration} 秒"
            logger.info(
                f"用户 {user_id} 在群聊中被 {event.get_sender_name()} 执行 {action}"
            )
            return ToolExecResult(f"已对 QQ:{user_id} 执行{action}。")
        except Exception as e:
            logger.error(f"禁言用户 {user_id} 失败: {e}")
            return ToolExecResult(f"禁言失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class SetGroupSpecialTitleTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """设置群头衔工具"""

    name: str = "set_group_special_title"
    description: str = "为群成员设置专属头衔（需要群主权限或支持头衔的群）。重要提示：如果不知道对方的QQ号，请先调用 get_group_member_list 获取群成员列表。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "要设置头衔的用户的QQ号，必定为数字字符串，如 '12345678'",
                },
                "title": {
                    "type": "string",
                    "description": "新的群头衔，空字符串表示清除头衔",
                },
            },
            "required": ["user_id", "title"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_action")
            if not enabled:
                return ToolExecResult(msg)

            user_id = kwargs.get("user_id", "")
            title = kwargs.get("title", "")

            if not user_id:
                return ToolExecResult("请提供要设置头衔的用户QQ号")

            event = context.context.event
            group_id = event.get_group_id()
            if not group_id:
                return ToolExecResult("仅在群聊中才可以设置头衔。")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            await bot.set_group_special_title(
                group_id=int(group_id),
                user_id=int(user_id),
                special_title=str(title),
                duration=-1,
            )
            logger.info(
                f"用户 {user_id} 在群聊中被 {event.get_sender_name()} 设置头衔：{title}"
            )
            return ToolExecResult(f"已为 QQ:{user_id} 设置头衔：{title}。")
        except Exception as e:
            logger.error(f"设置头衔失败: {e}")
            return ToolExecResult(f"设置头衔失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class CancelGroupBanTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """解除禁言工具"""

    name: str = "cancel_group_ban"
    description: str = "在群聊中解除某用户的禁言。重要提示：如果不知道对方的QQ号，请先调用 get_group_member_list 获取群成员列表。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "要解禁的用户的QQ号，必定为数字字符串，如 '12345678'",
                },
            },
            "required": ["user_id"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_action")
            if not enabled:
                return ToolExecResult(msg)

            user_id = kwargs.get("user_id", "")
            if not user_id:
                return ToolExecResult("请提供要解禁的用户QQ号")

            event = context.context.event
            group_id = event.get_group_id()
            if not group_id:
                return ToolExecResult("仅在群聊中才可以解禁。")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            await bot.set_group_ban(
                group_id=int(group_id), user_id=int(user_id), duration=0
            )
            logger.info(f"用户 {user_id} 在群聊中被 {event.get_sender_name()} 解除禁言")
            return ToolExecResult(f"已解除 QQ:{user_id} 的禁言。")
        except Exception as e:
            logger.error(f"解禁用户 {user_id} 失败: {e}")
            return ToolExecResult(f"解除禁言失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class SetGroupCardTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """修改群名片工具"""

    name: str = "set_group_card"
    description: str = "修改群成员的群昵称（群名片）。重要提示：如果不知道对方的QQ号，请先调用 get_group_member_list 获取群成员列表。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "要改名的用户的QQ号，必定为数字字符串，如 '12345678'",
                },
                "card": {
                    "type": "string",
                    "description": "新的群昵称，空字符串表示清除昵称",
                },
            },
            "required": ["user_id", "card"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_action")
            if not enabled:
                return ToolExecResult(msg)

            user_id = kwargs.get("user_id", "")
            card = kwargs.get("card", "")

            if not user_id:
                return ToolExecResult("请提供要改名的用户QQ号")

            event = context.context.event
            group_id = event.get_group_id()
            if not group_id:
                return ToolExecResult("仅在群聊中才可以修改名片。")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            await bot.set_group_card(
                group_id=int(group_id),
                user_id=int(user_id),
                card=card,
            )
            logger.info(
                f"用户 {user_id} 在群聊中被 {event.get_sender_name()} 修改群昵称为【{card}】"
            )
            return ToolExecResult(f"已修改 QQ:{user_id} 的群昵称为【{card}】。")
        except Exception as e:
            logger.error(f"修改用户 {user_id} 群昵称失败: {e}")
            return ToolExecResult(f"修改群昵称失败: {e}")


@dataclass(config={"arbitrary_types_allowed": True})
class SetEssenceMsgTool(QQToolBase, FunctionTool[AstrAgentContext]):
    """设置精华消息工具"""

    name: str = "set_essence_msg"
    description: str = "将消息设置为群精华消息。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "要设精的消息ID",
                },
            },
            "required": ["message_id"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            enabled, msg = self._check_enabled("tool_group_action")
            if not enabled:
                return ToolExecResult(msg)

            message_id = kwargs.get("message_id", "")
            if not message_id:
                return ToolExecResult("请提供要设精的消息ID")

            bot = self._get_bot(context)
            if not bot:
                return ToolExecResult("无法获取Bot实例")

            event = context.context.event
            await bot.set_essence_msg(message_id=int(message_id))
            logger.info(f"消息 {message_id} 被 {event.get_sender_name()} 设为精华")
            return ToolExecResult(f"已设置消息 {message_id} 为精华。")
        except Exception as e:
            logger.error(f"设置消息 {message_id} 为精华失败: {e}")
            return ToolExecResult(f"设置精华消息失败: {e}")


# ============ 工具注册 ============


def register_llm_tools(plugin_instance) -> None:
    """注册所有LLM工具到 AstrBot"""

    # 创建工具实例
    tools = [
        GetGroupMemberListTool(),
        GetUserInfoTool(),
        GetGroupInfoTool(),
        PokeUserTool(),
        SetGroupBanTool(),
        SetGroupSpecialTitleTool(),
        CancelGroupBanTool(),
        SetGroupCardTool(),
        SetEssenceMsgTool(),
    ]

    # 注入配置
    for tool in tools:
        tool.inject_config(plugin_instance.cfg)

    # 注册到 AstrBot
    plugin_instance.context.add_llm_tools(*tools)

    logger.info(f"[QQAdmin] 已注册 {len(tools)} 个LLM工具")
