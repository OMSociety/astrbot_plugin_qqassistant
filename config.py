# config.py
from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping, MutableMapping
import random
from types import MappingProxyType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context
from astrbot.core.star.star_tools import StarTools
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_path


class ConfigNode:
    """
    配置节点, 把 dict 变成强类型对象。

    规则：
    - schema 来自子类类型注解
    - 声明字段：读写，回到底层 dict
    - 未声明字段和下划线字段：仅挂载属性，不写回
    - 支持 ConfigNode 多层嵌套（lazy + cache）
    """

    _SCHEMA_CACHE: dict[type, dict[str, type]] = {}
    _FIELDS_CACHE: dict[type, set[str]] = {}

    @classmethod
    def _schema(cls) -> dict[str, type]:
        return cls._SCHEMA_CACHE.setdefault(cls, get_type_hints(cls))

    @classmethod
    def _fields(cls) -> set[str]:
        return cls._FIELDS_CACHE.setdefault(
            cls,
            {k for k in cls._schema() if not k.startswith("_")},
        )

    @staticmethod
    def _is_optional(tp: type) -> bool:
        if get_origin(tp) in (Union, UnionType):
            return type(None) in get_args(tp)
        return False

    def __init__(self, data: MutableMapping[str, Any]):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_children", {})
        for key, tp in self._schema().items():
            if key.startswith("_"):
                continue
            if key in data:
                continue
            if hasattr(self.__class__, key):
                continue
            if self._is_optional(tp):
                continue
            logger.warning(f"[config:{self.__class__.__name__}] 缺少字段: {key}")

    def __getattr__(self, key: str) -> Any:
        if key in self._fields():
            value = self._data.get(key)
            tp = self._schema().get(key)

            if isinstance(tp, type) and issubclass(tp, ConfigNode):
                children: dict[str, ConfigNode] = self.__dict__["_children"]
                if key not in children:
                    if not isinstance(value, MutableMapping):
                        raise TypeError(
                            f"[config:{self.__class__.__name__}] "
                            f"字段 {key} 期望 dict，实际是 {type(value).__name__}"
                        )
                    children[key] = tp(value)
                return children[key]

            return value

        if key in self.__dict__:
            return self.__dict__[key]

        raise AttributeError(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in self._fields():
            self._data[key] = value
            return
        object.__setattr__(self, key, value)

    def raw_data(self) -> Mapping[str, Any]:
        """
        底层配置 dict 的只读视图
        """
        return MappingProxyType(self._data)

    def save_config(self) -> None:
        """
        保存配置到磁盘（仅允许在根节点调用）
        """
        if not isinstance(self._data, AstrBotConfig):
            raise RuntimeError(
                f"{self.__class__.__name__}.save_config() 只能在根配置节点上调用"
            )
        self._data.save_config()


# ============ 插件自定义配置 ==================


class PluginConfig(ConfigNode):
    divided_manage: bool
    default: dict

    _db_version = 3
    _plugin_name: str = "astrbot_plugin_qqassistant"

    def __init__(self, cfg: AstrBotConfig, context: Context):
        super().__init__(cfg)
        self.context = context
        self.admins_id = self._clean_ids(context.get_config().get("admins_id", []))

        self.data_dir = StarTools.get_data_dir(self._plugin_name)
        self.plugin_dir = Path(get_astrbot_plugin_path()) / self._plugin_name

        self.db_path = self.data_dir / f"qqadmin_data_v{self._db_version}.db"
        self.ban_lexicon_path = self.plugin_dir / "SensitiveLexicon.json"
        self.group_notice_dir = self.data_dir / "group_notice"
        self.group_notice_dir.mkdir(parents=True, exist_ok=True)
        self.curfew_file = self.data_dir / "curfew_data.json"
        if not self.curfew_file.exists():
            self.curfew_file.write_text("{}", encoding="utf-8")
        self.file_dir = self.data_dir / "file"
        self.file_dir.mkdir(parents=True, exist_ok=True)

        self.spamming_count = 5
        self.spamming_interval = 0.5

        # ========== 转发消息解析配置 ==========
        self.enable_forward_message_parsing = cfg.get(
            "forward_parse_enable",
            cfg.get("enable_forward_message_parsing", True),
        )
        raw_depth = cfg.get("forward_max_nesting_depth", 3)
        try:
            depth = int(raw_depth) if raw_depth is not None else 3
        except (ValueError, TypeError):
            logger.warning(f"[转发解析] forward_max_nesting_depth配置值'{raw_depth}'无法转换为整数，使用默认值3")
            depth = 3
        depth = max(0, min(depth, 10))
        self.forward_max_nesting_depth = depth
        self.include_sender_info = cfg.get("forward_include_sender_info", True)
        self.include_timestamp = cfg.get("forward_include_timestamp", True)

    @staticmethod
    def _clean_ids(ids: list) -> list[str]:
        """过滤并规范化数字 ID"""
        return [str(i) for i in ids if str(i).isdigit()]

    @property
    def tools(self) -> dict:
        """
        获取工具开关配置，兼容旧的 getattr 访问方式
        
        新版本使用分组开关：tool_group_info / tool_group_action / tool_group_search / tool_group_batch / tool_group_monitor
        旧版本使用独立开关：get_group_member_list / set_group_ban 等（向下兼容）
        """
        tools_data = self._data.get("tools", {})
        default_tools = {
            "tool_group_info": True,
            "tool_group_action": True,
            "tool_group_search": True,
            "tool_group_batch": True,
            "tool_group_monitor": True,
        }
        # 旧版独立开关到新版的映射
        legacy_to_group = {
            "get_group_member_list": "tool_group_info",
            "get_user_info": "tool_group_info",
            "get_group_info": "tool_group_info",
            "poke_user": "tool_group_action",
            "set_group_ban": "tool_group_action",
            "cancel_group_ban": "tool_group_action",
            "set_group_card": "tool_group_action",
            "set_group_special_title": "tool_group_action",
            "set_essence_msg": "tool_group_action",
            "search_group_history": "tool_group_search",
            "search_other_chats": "tool_group_search",
            "get_scene_info": "tool_group_search",
            "batch_ban": "tool_group_batch",
            "batch_set_card": "tool_group_batch",
            "batch_send_msg": "tool_group_batch",
            "spamming_ban": "tool_group_monitor",
            "event_monitoring": "tool_group_monitor",
        }

        result = default_tools.copy()
        # 先应用旧版独立开关映射到分组
        for old_key, group_key in legacy_to_group.items():
            if old_key in tools_data:
                result[group_key] = tools_data[old_key]
        # 再应用新版分组开关（优先）
        for key, value in tools_data.items():
            if key in default_tools:
                result[key] = value
        return result
