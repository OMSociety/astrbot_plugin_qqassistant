"""
批量操作 LLM 工具模块

提供LLM可调用的批量操作工具（FunctionTool方式）：
- 批量禁言
- 批量修改群名片
- 批量发送消息
"""

from typing import Any, List, Dict

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot import logger
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.agent.run_context import ContextWrapper


class BatchToolBase:
    """批量操作工具基类"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.cfg = None
    
    def inject_config(self, cfg):
        self.cfg = cfg


@dataclass(config=dict(arbitrary_types_allowed=True))
class BatchBanTool(BatchToolBase, FunctionTool[AstrAgentContext]):
    """批量禁言工具"""
    
    name: str = "batch_ban"
    description: str = "批量禁言多个用户（管理员专用）。重要提示：如果不知道对方的QQ号，请先调用 get_group_member_list 获取群成员列表。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_ids": {
                    "type": "array",
                    "description": "要禁言的用户QQ号列表（JSON数组格式，如 ['123','456']）",
                    "items": {"type": "string"},
                },
                "duration": {
                    "type": "number",
                    "description": "禁言时长（秒），范围0~86400，0表示解除禁言",
                },
            },
            "required": ["user_ids", "duration"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            event = context.context.event
            
            # 检查工具开关
            if self.cfg and not self.cfg.tools.get("tool_group_batch", True):
                return ToolExecResult("批量操作功能已关闭~")
            
            # 检查管理员权限
            if not event.is_admin():
                return ToolExecResult("权限不足，仅管理员可用此功能。")
            
            user_ids = kwargs.get("user_ids", [])
            duration = kwargs.get("duration", 60)
            
            if not user_ids:
                return ToolExecResult("请提供要禁言的用户QQ号列表")
            
            bot = event.bot
            
            success_count = 0
            fail_count = 0
            fail_list = []
            
            for user_id in user_ids:
                try:
                    await bot.set_group_ban(
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
            return ToolExecResult("，".join(result_parts))
        except Exception as e:
            logger.error(f"批量禁言失败: {e}")
            return ToolExecResult(f"批量禁言失败: {e}")


@dataclass(config=dict(arbitrary_types_allowed=True))
class BatchSetCardTool(BatchToolBase, FunctionTool[AstrAgentContext]):
    """批量修改群名片工具"""
    
    name: str = "batch_set_card"
    description: str = "批量修改多个用户的群名片（管理员专用）。重要提示：如果不知道对方的QQ号，请先调用 get_group_member_list 获取群成员列表。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_cards": {
                    "type": "object",
                    "description": "用户QQ到新群名片的映射（JSON对象格式，如 {'123':'新名片1','456':'新名片2'}），键为QQ号，值为新名片",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["user_cards"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            event = context.context.event
            
            # 检查工具开关
            if self.cfg and not self.cfg.tools.get("tool_group_batch", True):
                return ToolExecResult("批量操作功能已关闭~")
            
            if not event.is_admin():
                return ToolExecResult("权限不足，仅管理员可用此功能。")
            
            user_cards = kwargs.get("user_cards", {})
            
            if not user_cards:
                return ToolExecResult("请提供要修改的用户名片映射")
            
            bot = event.bot
            
            success_count = 0
            fail_count = 0
            fail_list = []
            
            for user_id, new_card in user_cards.items():
                try:
                    await bot.set_group_card(
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
            return ToolExecResult("，".join(result_parts))
        except Exception as e:
            logger.error(f"批量改名片失败: {e}")
            return ToolExecResult(f"批量改名片失败: {e}")


@dataclass(config=dict(arbitrary_types_allowed=True))
class BatchSendMsgTool(BatchToolBase, FunctionTool[AstrAgentContext]):
    """批量发送群消息工具"""
    
    name: str = "batch_send_msg"
    description: str = "向多个群发送消息（管理员专用）。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "group_ids": {
                    "type": "array",
                    "description": "要发送到的群号列表（JSON数组格式，如 ['123456','789012']）",
                    "items": {"type": "string"},
                },
                "message": {
                    "type": "string",
                    "description": "要发送的消息内容",
                },
            },
            "required": ["group_ids", "message"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        try:
            event = context.context.event
            
            # 检查工具开关
            if self.cfg and not self.cfg.tools.get("tool_group_batch", True):
                return ToolExecResult("批量操作功能已关闭~")
            
            if not event.is_admin():
                return ToolExecResult("权限不足，仅管理员可用此功能。")
            
            group_ids = kwargs.get("group_ids", [])
            message = kwargs.get("message", "")
            
            if not group_ids:
                return ToolExecResult("请提供要发送的群号列表")
            
            if not message:
                return ToolExecResult("请提供要发送的消息内容")
            
            bot = event.bot
            
            success_count = 0
            fail_count = 0
            fail_list = []
            
            for group_id in group_ids:
                try:
                    await bot.send_group_msg(
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
            return ToolExecResult("，".join(result_parts))
        except Exception as e:
            logger.error(f"批量发消息失败: {e}")
            return ToolExecResult(f"批量发消息失败: {e}")


def register_batch_tools(plugin_instance) -> None:
    """注册批量操作工具到 AstrBot"""
    from ..config import PluginConfig
    
    tools = [
        BatchBanTool(),
        BatchSetCardTool(),
        BatchSendMsgTool(),
    ]
    
    for tool in tools:
        tool.inject_config(plugin_instance.cfg)
    
    plugin_instance.context.add_llm_tools(*tools)
    
    logger.info(f"[QQAdmin] 已注册 {len(tools)} 个批量操作工具")
