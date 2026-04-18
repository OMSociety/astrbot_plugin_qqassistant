"""
批量操作工具类
"""
from typing import List, Dict, Any
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from ...config import PluginConfig
from ...data import QQAdminDB

class BatchToolsHandle:
    def __init__(self, cfg: PluginConfig, db: QQAdminDB):
        self.cfg = cfg
        self.db = db

    async def batch_ban(self, event: AiocqhttpMessageEvent, user_ids: List[str], duration: int) -> Dict[str, Any]:
        """
        批量禁言用户
        :param event: 消息事件
        :param user_ids: 用户QQ列表
        :param duration: 禁言时长（秒）
        :return: 操作结果
        """
        if not event.is_admin():
            return {"success": False, "msg": "权限不足"}
        
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for user_id in user_ids:
            try:
                await event.bot.set_group_ban(group_id=event.group_id, user_id=user_id, duration=duration)
                success_count +=1
            except Exception as e:
                fail_count +=1
                fail_list.append({"user_id": user_id, "error": str(e)})
        
        return {
            "success": True,
            "total": len(user_ids),
            "success_count": success_count,
            "fail_count": fail_count,
            "fail_list": fail_list
        }

    async def batch_set_card(self, event: AiocqhttpMessageEvent, user_cards: Dict[str, str]) -> Dict[str, Any]:
        """
        批量修改群名片
        :param event: 消息事件
        :param user_cards: {user_id: new_card}
        :return: 操作结果
        """
        if not event.is_admin():
            return {"success": False, "msg": "权限不足"}
        
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for user_id, new_card in user_cards.items():
            try:
                await event.bot.set_group_card(group_id=event.group_id, user_id=user_id, card=new_card)
                success_count +=1
            except Exception as e:
                fail_count +=1
                fail_list.append({"user_id": user_id, "error": str(e)})
        
        return {
            "success": True,
            "total": len(user_cards),
            "success_count": success_count,
            "fail_count": fail_count,
            "fail_list": fail_list
        }

    async def batch_send_msg(self, event: AiocqhttpMessageEvent, group_ids: List[str], message: str) -> Dict[str, Any]:
        """
        批量发送群消息
        :param event: 消息事件
        :param group_ids: 群号列表
        :param message: 消息内容
        :return: 操作结果
        """
        if not event.is_admin():
            return {"success": False, "msg": "权限不足"}
        
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for group_id in group_ids:
            try:
                await event.bot.send_group_msg(group_id=group_id, message=message)
                success_count +=1
            except Exception as e:
                fail_count +=1
                fail_list.append({"group_id": group_id, "error": str(e)})
        
        return {
            "success": True,
            "total": len(group_ids),
            "success_count": success_count,
            "fail_count": fail_count,
            "fail_list": fail_list
        }