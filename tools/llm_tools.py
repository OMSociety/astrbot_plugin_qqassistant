"""
LLM工具模块

提供LLM可调用的QQ群管工具函数，包括：
- 获取群成员列表
- 获取用户信息
- 戳一戳
- 禁言/解禁
- 设置群头衔
- 修改群名片
- 设置精华消息
"""

import re
from typing import TYPE_CHECKING, Generator, Any, Optional

from astrbot import logger
from astrbot.api.event import filter
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from ..config import PluginConfig

if TYPE_CHECKING:
    from astrbot.api.star import Context


class LLMToolBase:
    """LLM工具基类，提供统一的封装"""

    def __init__(self, cfg: PluginConfig):
        self.cfg = cfg

    @staticmethod
    def _stop_and_yield(event: AiocqhttpMessageEvent, message: str = ""):
        """
        统一的停止事件和返回消息逻辑
        Args:
            event: 消息事件
            message (str): 要返回的消息，为空则返回None
        """
        event.stop_event()
        if message:
            return message
        return None

    @staticmethod
    def _try_except_wrapper(func_name: str):
        """
        异常处理装饰器工厂
        Args:
            func_name: 函数名称，用于日志记录
        """
        def decorator(func):
            async def wrapper(self, event: AiocqhttpMessageEvent, *args, **kwargs):
                try:
                    result = await func(self, event, *args, **kwargs)
                    return result
                except Exception as e:
                    logger.error(f"{func_name}失败: {e}")
                    return f"{func_name}失败: {e}"
            return wrapper
        return decorator

    @classmethod
    def _check_tool_enabled(cls, cfg: PluginConfig, tool_key: str) -> tuple[bool, str]:
        """
        检查工具开关是否启用
        
        Args:
            cfg (PluginConfig): 插件配置对象
            tool_key (str): 工具配置键名
        
        Returns:
            tuple[bool, str]: (是否启用, 错误消息或空字符串)
        """
        tools_cfg = cfg.tools
        if not tools_cfg.get(tool_key, True):
            return False, f"该功能已关闭~"
        return True, ""


class LLMGetGroupMemberList(LLMToolBase):
    """
    获取群成员列表工具
    
    功能说明：
    - 返回当前群的所有成员信息，包括昵称、群名片、QQ号、身份（群主/管理员/成员）、头衔
    - 自动按名称排序便于查找
    
    使用场景：
    在调用需要 user_id 的工具（如禁言、设置头衔、戳一戳）前，应先调用本工具获取群成员列表和对应的QQ号码。
    
    source: astrbot_plugin_qqassistant
    """

    @filter.llm_tool()
    async def llm_get_group_member_list(self, event: AiocqhttpMessageEvent) -> Generator[str, Any, None]:
        """
        获取当前群聊成员列表（昵称/名片/QQ/身份/头衔）

        重要提示：在调用需要 user_id 的工具（如禁言、设置头衔、戳一戳）前，应先调用本工具获取群成员列表和对应的QQ号码。
        
        Returns:
            str: 格式化的成员列表，格式为 "[身份] 显示名称 (QQ: QQ号) [头衔信息]"
        """
        if not self.cfg.tools.get("tool_group_info", True):
            yield "该功能已关闭~"
            return
        try:
            group_id = event.get_group_id()
            if not group_id:
                yield "当前是私聊会话，无法获取群成员列表。"
                return

            member_list = await event.bot.get_group_member_list(
                group_id=int(group_id), no_cache=True
            )
            if not member_list:
                yield "获取群成员列表失败或列表为空。"
                return

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

            event.stop_event()
            yield "\n".join(out)
        except Exception as e:
            logger.error(f"获取群成员列表失败: {e}")
            yield f"获取群成员列表失败: {e}"


class LLMGetUserInfo(LLMToolBase):
    """
    获取用户信息工具
    
    功能说明：
    - 群聊中优先获取群成员详细信息（包含群名片、身份、头衔、等级）
    - 私聊或非群成员获取陌生人基本信息
    
    source: astrbot_plugin_qqassistant
    """

    @filter.llm_tool()
    async def llm_get_user_info(self, event: AiocqhttpMessageEvent, qq_id: Optional[str] = None) -> Generator[str, Any, None]:
        """
        获取QQ用户信息（群聊优先取群成员信息，否则取陌生人信息）

        Args:
            qq_id (str): 要查询的QQ号，默认为空表示查询消息发送者
        
        Returns:
            str: 用户信息，格式为多行文本，包含QQ号、昵称、群名片、身份、头衔、等级等信息
        """
        if not self.cfg.tools.get("tool_group_info", True):
            yield "该功能已关闭~"
            return
        try:
            target_id = str(qq_id) if qq_id else str(event.get_sender_id())
            if not target_id:
                yield "未指定查询对象。"
                return

            group_id = event.get_group_id()
            if group_id:
                info = await event.bot.get_group_member_info(
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
                event.stop_event()
                yield "\n".join(s)
                return

            info = await event.bot.get_stranger_info(user_id=int(target_id), no_cache=True)
            s = [f"QQ: {target_id}", f"昵称: {info.get('nickname', '未知')}"]
            event.stop_event()
            yield "\n".join(s)
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            yield f"获取用户信息失败: {e}"


class LLMGetGroupInfo(LLMToolBase):
    """
    获取群信息工具
    
    功能说明：
    - 获取群的详细信息，包括群号、群名、人数、描述等
    - 用于让LLM了解当前群的基本情况
    
    source: astrbot_plugin_qqassistant
    """

    @staticmethod
    @filter.llm_tool(
        description="获取当前群的详细信息，包括群号、群名、群人数、群主、描述等"
    )
    async def llm_get_group_info(self, event: AiocqhttpMessageEvent) -> Generator[str, Any, None]:
        """
        获取当前群聊的信息

        
        Returns:
            str: 群信息，格式为多行文本，包含群号、群名、人数、群主、描述等
        """
        if not self.cfg.tools.get("tool_group_info", True):
            yield "该功能已关闭~"
            return
        try:
            group_id = event.get_group_id()
            if not group_id:
                yield "当前是私聊会话，无法获取群信息。"
                return

            info = await event.bot.get_group_info(group_id=int(group_id))
            if not info:
                yield "获取群信息失败。"
                return

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
                import time
                create_time = time.strftime("%Y-%m-%d", time.localtime(info.get("group_create_time")))
                s.append(f"创建时间: {create_time}")

            event.stop_event()
            yield "\n".join(s)
        except Exception as e:
            logger.error(f"获取群信息失败: {e}")
            yield f"获取群信息失败: {e}"


class LLMPokeUser(LLMToolBase):
    """
    戳一戳工具
    
    功能说明：
    - 群聊中戳指定用户
    - 私聊中戳好友
    - 自动判断场景
    
    source: astrbot_plugin_qqassistant
    """

    @filter.llm_tool()
    async def llm_poke_user(self, event: AiocqhttpMessageEvent, qq_id: str) -> Generator[str, Any, None]:
        """
        戳一戳指定用户（群聊/私聊自动判断）

        重要提示：如果不知道对方的QQ号，请先调用 llm_get_group_member_list 获取群成员列表。
        
        Args:
            qq_id (str): 要戳的用户的QQ号，必定为数字字符串，如 "12345678"
        
        Returns:
            str: 操作结果消息
        """
        if not self.cfg.tools.get("tool_group_action", True):
            yield "该功能已关闭~"
            return
        try:
            group_id = event.get_group_id()
            if group_id:
                await event.bot.group_poke(group_id=int(group_id), user_id=int(qq_id))
            else:
                await event.bot.friend_poke(user_id=int(qq_id))
            logger.info(f"戳一戳用户 {qq_id} 成功")
            event.stop_event()
            yield f"已戳一戳用户 {qq_id}。"
        except Exception as e:
            logger.error(f"戳一戳失败: {e}")
            yield f"戳一戳失败: {e}"


class LLMSetGroupBanUser(LLMToolBase):
    """
    禁言工具
    
    功能说明：
    - 在群聊中对指定用户进行禁言
    - 支持设置禁言时长（0秒表示解除禁言）
    - 自动检查权限关系（机器人 vs 目标用户）
    
    source: astrbot_plugin_qqassistant
    """

    @filter.llm_tool()
    async def llm_set_group_ban_user(self, event: AiocqhttpMessageEvent, user_id: str, duration: int) -> Generator[str, Any, None]:
        """
        对个人进行禁言（带简单权限判定提示）

        重要提示：如果不知道对方的QQ号，请先调用 llm_get_group_member_list 获取群成员列表。
        
        Args:
            user_id (str): 要禁言的用户的QQ号，必定为数字字符串，如 "12345678"
            duration (int): 禁言持续时间（秒），范围为0~86400, 0表示取消禁言
        
        Returns:
            str: 操作结果消息，包含成功信息或权限不足提示
        """
        if not self.cfg.tools.get("tool_group_action", True):
            yield "该功能已关闭~"
            return
        try:
            group_id = event.get_group_id()
            if not group_id:
                yield "仅在群聊中才可以禁言。"
                return

            role_map = {"owner": "群主", "admin": "管理员", "member": "成员"}
            try:
                login = await event.bot.get_login_info()
                bot_id = str(login.get("user_id"))
                bot_info = await event.bot.get_group_member_info(
                    group_id=int(group_id), user_id=int(bot_id), no_cache=True
                )
                tgt_info = await event.bot.get_group_member_info(
                    group_id=int(group_id), user_id=int(user_id), no_cache=True
                )
                bot_role = bot_info.get("role", "member")
                tgt_role = tgt_info.get("role", "member")
                if bot_role == "admin" and tgt_role != "member":
                    yield f"禁言失败：权限不足。你的身份：{role_map.get(bot_role)}，对方的身份：{role_map.get(tgt_role)}"
                    return
                if bot_role == "member":
                    yield "禁言失败：机器人不是管理员/群主。"
                    return
                if bot_role == "owner" and tgt_role == "owner":
                    yield "禁言失败：不能对群主禁言。"
                    return
            except Exception:
                pass

            await event.bot.set_group_ban(
                group_id=int(group_id), user_id=int(user_id), duration=int(duration)
            )
            action = "解除禁言" if int(duration) == 0 else f"禁言 {duration} 秒"
            logger.info(f"用户：{user_id}在群聊中被：{event.get_sender_name()}执行{action}")
            event.stop_event()
            yield f"已对 QQ:{user_id} 执行{action}。"
        except Exception as e:
            logger.error(f"禁言用户 {user_id} 失败: {e}")
            yield f"禁言失败: {e}"


class LLMSetGroupSpecialTitle(LLMToolBase):
    """
    设置群头衔工具
    
    功能说明：
    - 为群成员设置专属头衔
    - 需要群主权限或支持头衔的群
    
    source: astrbot_plugin_qqassistant
    """

    @staticmethod
    @filter.llm_tool(
        description="为群成员设置专属头衔（需要群主权限或支持头衔的群）。参数：user_id-用户QQ号，title-新头衔（空字符串清除头衔）"
    )
    async def llm_set_group_special_title(self, event: AiocqhttpMessageEvent, user_id: str, title: str) -> Generator[str, Any, None]:
        """
        为群成员设置专属头衔（需要群主权限或支持头衔的群）

        重要提示：如果不知道对方的QQ号，请先调用 llm_get_group_member_list 获取群成员列表。
        
        Args:
            user_id (str): 要设置头衔的用户的QQ号，必定为数字字符串，如 "12345678"
            title (str): 新的群头衔，空字符串表示清除头衔
        
        Returns:
            str: 操作结果消息
        """
        if not self.cfg.tools.get("tool_group_action", True):
            yield "该功能已关闭~"
            return
        try:
            group_id = event.get_group_id()
            if not group_id:
                yield "仅在群聊中才可以设置头衔。"
                return

            await event.bot.set_group_special_title(
                group_id=int(group_id), user_id=int(user_id), special_title=str(title), duration=-1
            )
            logger.info(f"用户：{user_id}在群聊中被：{event.get_sender_name()}设置头衔：{title}")
            event.stop_event()
            yield f"已为 QQ:{user_id} 设置头衔：{title}。"
        except Exception as e:
            logger.error(f"设置头衔失败: {e}")
            yield f"设置头衔失败: {e}"


class LLMCancelGroupBan(LLMToolBase):
    """
    解除禁言工具
    
    功能说明：
    - 在群聊中解除某用户的禁言
    - 相当于设置禁言时长为0秒
    
    source: astrbot_plugin_qqassistant
    """

    @filter.llm_tool(
        description="在群聊中解除某用户的禁言。参数：user_id-要解禁的用户的QQ号"
    )
    async def llm_cancel_group_ban(self, 
        event: AiocqhttpMessageEvent, user_id: str
    ) -> Generator[str, Any, None]:
        """
        在群聊中解除某用户的禁言。
        重要提示：如果不知道对方的QQ号，请先调用 llm_get_group_member_list 获取群成员列表。
        
        Args:
            user_id (str): 要解禁的用户的QQ账号，必定为一串数字，如 "12345678"
        
        Returns:
            str: 操作结果消息
        """
        if not self.cfg.tools.get("tool_group_action", True):
            yield "该功能已关闭~"
            return
        try:
            await event.bot.set_group_ban(
                group_id=int(event.get_group_id()),
                user_id=int(user_id),
                duration=0,
            )
            logger.info(f"用户 {user_id} 在群聊中被 {event.get_sender_name()} 解除禁言")
            event.stop_event()
            yield f"已解除 QQ:{user_id} 的禁言。"
        except Exception as e:
            logger.error(f"解禁用户 {user_id} 失败: {e}")
            yield f"解除禁言失败: {e}"


class LLMSetGroupCard(LLMToolBase):
    """
    修改群名片工具
    
    功能说明：
    - 修改群成员的群昵称（群名片）
    - 设置为空字符串表示清除昵称
    
    source: astrbot_plugin_qqassistant
    """

    @filter.llm_tool(
        description="修改群成员的群昵称（群名片）。参数：user_id-用户QQ号，card-新的群昵称（空字符串清除）"
    )
    async def llm_set_group_card(self, 
        event: AiocqhttpMessageEvent, user_id: str, card: str
    ) -> Generator[str, Any, None]:
        """
        修改群成员的群昵称（群名片）。
        重要提示：如果不知道对方的QQ号，请先调用 llm_get_group_member_list 获取群成员列表。
        
        Args:
            user_id (str): 要改名的用户的QQ账号，必定为一串数字，如 "12345678"
            card (str): 新的群昵称，空字符串表示清除昵称
        
        Returns:
            str: 操作结果消息
        """
        if not self.cfg.tools.get("tool_group_action", True):
            yield "该功能已关闭~"
            return
        try:
            await event.bot.set_group_card(
                group_id=int(event.get_group_id()),
                user_id=int(user_id),
                card=card,
            )
            logger.info(f"用户 {user_id} 在群聊中被 {event.get_sender_name()} 修改群昵称为【{card}】")
            event.stop_event()
            yield f"已修改 QQ:{user_id} 的群昵称为【{card}】。"
        except Exception as e:
            logger.error(f"修改用户 {user_id} 群昵称失败: {e}")
            yield f"修改群昵称失败: {e}"


class LLMSetEssenceMsg(LLMToolBase):
    """
    设置精华消息工具
    
    功能说明：
    - 将消息设置为群精华消息
    - 需要Bot具有相应权限
    
    source: astrbot_plugin_qqassistant
    """

    @filter.llm_tool(
        description="将消息设置为群精华消息。参数：message_id-要设精的消息ID"
    )
    async def llm_set_essence_msg(
        self, event: AiocqhttpMessageEvent, message_id: str
    ) -> Generator[str, Any, None]:
        """
        将消息设置为群精华消息。
        
        Args:
            message_id (str): 要设精的消息ID
        
        Returns:
            str: 操作结果消息
        """
        if not self.cfg.tools.get("tool_group_action", True):
            yield "该功能已关闭~"
            return
        try:
            await event.bot.set_essence_msg(message_id=int(message_id))
            logger.info(f"消息 {message_id} 被 {event.get_sender_name()} 设为精华")
            event.stop_event()
            yield f"已设置消息 {message_id} 为精华。"
        except Exception as e:
            logger.error(f"设置消息 {message_id} 为精华失败: {e}")
            yield f"设置精华消息失败: {e}"


# ============ 工具注册 ============
def register_llm_tools(plugin_instance) -> None:
    """
    注册所有LLM工具到插件实例
    
    Args:
        plugin_instance: 插件实例
    """
    setattr(plugin_instance, 'get_group_member_list', LLMGetGroupMemberList.llm_get_group_member_list)
    setattr(plugin_instance, 'get_group_info', LLMGetGroupInfo.llm_get_group_info)
    setattr(plugin_instance, 'get_user_info', LLMGetUserInfo.llm_get_user_info)
    setattr(plugin_instance, 'poke_user', LLMPokeUser.llm_poke_user)
    setattr(plugin_instance, 'set_group_ban', LLMSetGroupBanUser.llm_set_group_ban_user)
    setattr(plugin_instance, 'set_group_special_title', LLMSetGroupSpecialTitle.llm_set_group_special_title)
    setattr(plugin_instance, 'cancel_group_ban', LLMCancelGroupBan.llm_cancel_group_ban)
    setattr(plugin_instance, 'set_group_card', LLMSetGroupCard.llm_set_group_card)
    setattr(plugin_instance, 'set_essence_msg', LLMSetEssenceMsg.llm_set_essence_msg)
