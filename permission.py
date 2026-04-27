import inspect
from collections.abc import AsyncGenerator, Awaitable, Callable
from functools import wraps
from typing import Any, cast

from astrbot import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .config import PluginConfig
from .utils import get_ats


class PermLevel:
    """
    定义用户的权限等级。数字越小，权限越高。
    """

    SUPERUSER = 0
    OWNER = 1
    ADMIN = 2
    HIGH = 3
    MEMBER = 4
    UNKNOWN = 5

    def __str__(self):
        return {
            self.SUPERUSER: "超管",
            self.OWNER: "群主",
            self.ADMIN: "管理员",
            self.HIGH: "高级成员",
            self.MEMBER: "成员",
            self.UNKNOWN: "未知/无权限",
        }.get(self, "未知/无权限")

    def __repr__(self):
        return f"<PermLevel.{self.name}>"

    def __eq__(self, other):
        if isinstance(other, PermLevel):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.value < other.value

    def __le__(self, other):
        return self.value <= other.value

    def __gt__(self, other):
        return self.value > other.value

    def __ge__(self, other):
        return self.value >= other.value

    def __int__(self):
        return self.value


class PermissionManager:
    is_initialized = False

    def __init__(self):
        self.cfg: PluginConfig | None = None

    def lazy_init(self, config: PluginConfig):
        if self.is_initialized:
            raise RuntimeError("PermissionManager already initialized")
        self.cfg = config
        self.is_initialized = True

    def _is_admin_only_tool(self, tool_key: str) -> bool:
        """检查工具是否始终仅管理员可用"""
        admin_only_tools = (self.cfg.permissions or {}).get("admin_only_tools", []) or []
        return tool_key in admin_only_tools

    async def get_perm_level(
        self, event: AiocqhttpMessageEvent, user_id: str | int
    ) -> int:
        group_id = event.get_group_id()
        if int(group_id) == 0 or int(user_id) == 0:
            return PermLevel.UNKNOWN
        if self.cfg and str(user_id) in self.cfg.admins_id:
            return PermLevel.SUPERUSER
        try:
            info = await event.bot.get_group_member_info(
                group_id=int(group_id), user_id=int(user_id), no_cache=True
            )
        except Exception:
            return PermLevel.UNKNOWN
        role = info.get("role", "unknown")
        level = int(info.get("level", 0))
        match role:
            case "owner":
                return PermLevel.OWNER
            case "admin":
                return PermLevel.ADMIN
            case "member":
                return (
                    PermLevel.HIGH
                    if self.cfg and level >= self.cfg.level_threshold
                    else PermLevel.MEMBER
                )
            case _:
                return PermLevel.UNKNOWN

    async def perm_block(
        self,
        event: AiocqhttpMessageEvent,
        bot_perm: int,
        tool_key: str,
        check_at: bool = True,
    ) -> str | None:
        """检查用户是否有权限执行操作，返回错误信息或 None 表示通过"""
        user_level = await self.get_perm_level(event, user_id=event.get_sender_id())

        # 工具权限判断：默认所有工具对成员开放，只有在 admin_only_tools 中的才需要管理员权限
        if self._is_admin_only_tool(tool_key):
            required_level = PermLevel.ADMIN
        else:
            required_level = PermLevel.MEMBER  # 普通成员即可

        if user_level > required_level:
            return f"你没有{required_level}权限哦~"

        bot_level = await self.get_perm_level(event, user_id=event.get_self_id())
        if bot_level > bot_perm:
            return f"我没有{bot_perm}权限"

        if check_at:
            for at_id in get_ats(event):
                at_level = await self.get_perm_level(event, user_id=at_id)
                if bot_level >= at_level:
                    return f"我动不了{at_level}~"

        return None


perm_manager = PermissionManager()


def perm_required(
    bot_perm: int = PermLevel.ADMIN,
    tool_key: str | None = None,
    check_at: bool = True,
):
    """
    权限检查装饰器。
    :param tool_key: 工具标识符，对应 permissions 配置中的工具名。
    :param bot_perm: Bot 执行此命令所需的最低权限等级。
    :param check_at: 是否检查"是否有权对被@者实施操作"。
    """

    def decorator(
        func: Callable[..., AsyncGenerator[Any, Any] | Awaitable[Any]],
    ) -> Callable[..., AsyncGenerator[Any, Any]]:
        actual_key = tool_key or func.__name__

        @wraps(func)
        async def wrapper(
            plugin_instance: Any,
            event: AiocqhttpMessageEvent,
            *args: Any,
            **kwargs: Any,
        ) -> AsyncGenerator[Any, Any]:

            if event.platform_meta.name != "aiocqhttp":
                return

            if event.is_private_chat():
                return

            if not perm_manager.is_initialized:
                logger.error(
                    f"PermissionManager 未初始化（尝试访问权限项：{tool_key}）"
                )
                yield event.plain_result("内部错误：权限系统未正确加载")
                event.stop_event()
                return

            result = await perm_manager.perm_block(
                event, bot_perm=bot_perm, tool_key=actual_key, check_at=check_at
            )
            if result:
                yield event.plain_result(result)
                event.stop_event()
                return

            if inspect.isasyncgenfunction(func):
                async for item in func(plugin_instance, event, *args, **kwargs):
                    yield item
            else:
                await cast(
                    Awaitable[Any], func(plugin_instance, event, *args, **kwargs)
                )

        return wrapper

    return decorator
