"""
批量操作 LLM 工具模块

提供LLM可调用的批量操作工具，包括：
- 批量禁言
- 批量修改群名片
- 批量发送消息
"""

from typing import TYPE_CHECKING, Generator, Any, List, Dict

from astrbot import logger
from astrbot.api.event import filter
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

if TYPE_CHECKING:
    from ..config import PluginConfig


class LLMBatchTools:
    """
    批量操作 LLM 工具
    
    功能说明：
    - 批量禁言：一次性对多个用户执行禁言操作
    - 批量改名片：一次性修改多个用户的群名片
    - 批量发消息：向多个群发送相同消息
    
    source: astrbot_plugin_qqassistant
    """

    @staticmethod
    @filter.llm_tool(
        description="批量禁言多个用户。参数：user_ids-用户QQ号列表（JSON数组格式，如 [\"123\",\"456\"]），duration-禁言时长（秒，0表示解禁）"
    )
    async def batch_ban(
        event: AiocqhttpMessageEvent,
        user_ids: List[str],
        duration: int
    ) -> Generator[str, Any, None]:
        """
        批量禁言多个用户（管理员专用）
        重要提示：如果不知道对方的QQ号，请先调用 llm_get_group_member_list 获取群成员列表。
        
        Args:
            user_ids (list): 要禁言的用户QQ号列表，如 ["123", "456"]
            duration (int): 禁言时长（秒），0表示解除禁言
        
        Returns:
            str: 操作结果，包含成功数、失败数和失败详情
        """
        if not event.is_admin():
            yield "权限不足，仅管理员可用此功能。"
            return
        
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for user_id in user_ids:
            try:
                await event.bot.set_group_ban(
                    group_id=event.group_id,
                    user_id=int(user_id),
                    duration=int(duration)
                )
                success_count += 1
            except Exception as e:
                fail_count += 1
                fail_list.append(f"QQ:{user_id}（{str(e)[:30]}）")
        
        result_parts = [f"批量禁言完成：成功 {success_count} 人"]
        if fail_count > 0:
            result_parts.append(f"失败 {fail_count} 人：{', '.join(fail_list[:3])}")
            if fail_count > 3:
                result_parts.append(f"...（还有 {fail_count - 3} 人失败）")
        
        logger.info(f"批量禁言：成功{success_count}人，失败{fail_count}人")
        event.stop_event()
        yield "，".join(result_parts) if len(result_parts) > 1 else result_parts[0]

    @staticmethod
    @filter.llm_tool(
        description="批量修改多个用户的群名片。参数：user_cards-JSON对象格式，如 {\"123\":\"新名片1\",\"456\":\"新名片2\"}，键为QQ号，值为新名片"
    )
    async def batch_set_card(
        event: AiocqhttpMessageEvent,
        user_cards: Dict[str, str]
    ) -> Generator[str, Any, None]:
        """
        批量修改群名片（管理员专用）
        重要提示：如果不知道对方的QQ号，请先调用 llm_get_group_member_list 获取群成员列表。
        
        Args:
            user_cards (dict): 用户QQ到新群名片的映射，如 {"123": "新名片1", "456": "新名片2"}
        
        Returns:
            str: 操作结果
        """
        if not event.is_admin():
            yield "权限不足，仅管理员可用此功能。"
            return
        
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for user_id, new_card in user_cards.items():
            try:
                await event.bot.set_group_card(
                    group_id=event.group_id,
                    user_id=int(user_id),
                    card=str(new_card)
                )
                success_count += 1
            except Exception as e:
                fail_count += 1
                fail_list.append(f"QQ:{user_id}（{str(e)[:30]}）")
        
        result_parts = [f"批量改名片完成：成功 {success_count} 人"]
        if fail_count > 0:
            result_parts.append(f"失败 {fail_count} 人：{', '.join(fail_list[:3])}")
            if fail_count > 3:
                result_parts.append(f"...（还有 {fail_count - 3} 人失败）")
        
        logger.info(f"批量改名片：成功{success_count}人，失败{fail_count}人")
        event.stop_event()
        yield "，".join(result_parts) if len(result_parts) > 1 else result_parts[0]

    @staticmethod
    @filter.llm_tool(
        description="向多个群发送消息。参数：group_ids-群号列表（JSON数组格式，如 [\"123456\",\"789012\"]），message-要发送的消息内容"
    )
    async def batch_send_msg(
        event: AiocqhttpMessageEvent,
        group_ids: List[str],
        message: str
    ) -> Generator[str, Any, None]:
        """
        批量发送群消息（管理员专用）
        
        Args:
            group_ids (list): 要发送到的群号列表，如 ["123456", "789012"]
            message (str): 要发送的消息内容
        
        Returns:
            str: 操作结果
        """
        if not event.is_admin():
            yield "权限不足，仅管理员可用此功能。"
            return
        
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for group_id in group_ids:
            try:
                await event.bot.send_group_msg(
                    group_id=int(group_id),
                    message=str(message)
                )
                success_count += 1
            except Exception as e:
                fail_count += 1
                fail_list.append(f"群{group_id}（{str(e)[:30]}）")
        
        result_parts = [f"批量发消息完成：成功发送至 {success_count} 个群"]
        if fail_count > 0:
            result_parts.append(f"失败 {fail_count} 个群：{', '.join(fail_list[:3])}")
            if fail_count > 3:
                result_parts.append(f"...（还有 {fail_count - 3} 个群失败）")
        
        logger.info(f"批量发消息：成功{success_count}群，失败{fail_count}群")
        event.stop_event()
        yield "，".join(result_parts) if len(result_parts) > 1 else result_parts[0]
