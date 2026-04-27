"""LLM工具专用插件，提供QQ群管理功能"""

import asyncio
import random
import time

from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .config import PluginConfig
from .core import (
    BanproHandle,
    CurfewHandle,
    FileHandle,
    JoinHandle,
    LLMHandle,
    MemberHandle,
    NormalHandle,
    NoticeHandle,
)
from .data import QQAdminDB
from .permission import (
    perm_manager,
)
from .tools import register_llm_tools
from .tools.batch.batch_tools import BatchToolsHandle
from .tools.llm_cross_tools import register_cross_tools
from .unified_context.history_store import HistoryStore, MessageRecord
from .unified_context.prompt_builder import PromptBuilder
from .unified_context.scene_engine import SceneEngine
from .utils_pkg import print_logo
from .utils_pkg.forward_message_parser import ForwardMessageParser


class QQAdminPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.cfg = PluginConfig(config, context)
        self.db = QQAdminDB(self.cfg)
        self.normal = NormalHandle(self.cfg)
        self.notice = NoticeHandle(self, self.cfg)
        self.banpro = BanproHandle(self.cfg, self.db)
        self.join = JoinHandle(self.cfg, self.db)
        self.member = MemberHandle(self)
        self.file = FileHandle(self.cfg)
        self.curfew = CurfewHandle(self.context, self.cfg)
        self.llm = LLMHandle(self.context, self.cfg)
        # === 新增：批量操作工具 ===
        self.batch_tools = BatchToolsHandle(self.cfg, self.db)

        # === 新增：统一上下文引擎 ===
        self._context_enable = self.cfg.raw_data().get("context_enable", True)
        self._history_store = HistoryStore(
            max_messages=self.cfg.raw_data().get("context_max_history", 50),
            max_sessions=self.cfg.raw_data().get("context_max_sessions", 100),
        )
        self._prompt_builder = PromptBuilder(
            max_history=self.cfg.raw_data().get("context_inject_count", 8),
            max_chars=self.cfg.raw_data().get("context_max_chars", 2000),
        )
        self._scene_engine = None  # 懒初始化
        # === 新增：日志分级配置 ===
        self._log_level = self.cfg.raw_data().get("log_level", "INFO")

    async def initialize(self):
        await self.db.init()

        if not self.cfg.divided_manage:
            await self.db.reset_to_default()

        asyncio.create_task(self.curfew.initialize())

        perm_manager.lazy_init(self.cfg)

        if random.random() < 0.01:
            print_logo()

        # 注册 LLM 工具（FunctionTool 方式）
        register_llm_tools(self)

        # 注册批量操作工具（FunctionTool 方式）
        from .tools.batch_llm_tools import register_batch_tools

        register_batch_tools(self)

        # 注册跨上下文搜索工具（FunctionTool 方式）
        register_cross_tools(self)

        # 转发消息解析器
        self.forward_parser = ForwardMessageParser()

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成时"""
        if not self.curfew.curfew_managers:
            asyncio.create_task(self.curfew.initialize())

    # ========== 违禁词系统 ==========
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_ban_words(self, event: AiocqhttpMessageEvent):
        """自动检测违禁词，撤回并禁言"""
        if not event.is_admin():
            await self.banpro.on_ban_words(event)

    # ========== 刷屏检测 ==========
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def spamming_ban(self, event: AiocqhttpMessageEvent):
        """刷屏检测与禁言"""
        await self.banpro.spamming_ban(event)

    # ========== 进群审核 ==========
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def event_monitoring(self, event: AiocqhttpMessageEvent):
        """监听进群/退群事件"""
        await self.join.event_monitoring(event)

    # ====================================================================
    # 上下文感知 hooks
    # ====================================================================

    def _ensure_scene_engine(self, event):
        """懒初始化场景引擎"""
        if self._scene_engine is not None:
            return True
        bot_id = event.get_self_id()
        if not bot_id:
            return False
        bot_names = self.cfg.raw_data().get("bot_names", [])
        if not isinstance(bot_names, list):
            bot_names = []
        self._scene_engine = SceneEngine(bot_id=bot_id, bot_names=bot_names)
        return True

    @filter.platform_adapter_type(filter.PlatformAdapterType.ALL)
    async def on_message_context_record(self, event):
        """监听所有消息，记录到历史存储"""
        if not self._context_enable:
            return
        # 检查是否有转发消息或有效内容
        messages = event.get_messages()
        has_forward = any(c.__class__.__name__ == "Forward" for c in messages)
        has_normal_content = bool(event.message_str) or any(
            hasattr(c, "text") or c.__class__.__name__ == "Image" for c in messages
        )
        if not has_forward and not has_normal_content:
            return
        if not self._ensure_scene_engine(event):
            return

        # 尝试解析合并转发消息
        try:
            if self.cfg.enable_forward_message_parsing:
                await self.forward_parser.try_parse_and_replace(
                    event,
                    include_sender_info=self.cfg.include_sender_info,
                    include_timestamp=self.cfg.include_timestamp,
                    max_nesting_depth=self.cfg.forward_max_nesting_depth,
                    debug_mode=False,
                )
        except Exception:
            pass

        msg = self._scene_engine.extract_message(event)
        records, _ = await self._history_store.get_snapshot(event.unified_msg_origin)
        self._scene_engine.infer_addressee(msg, records)
        await self._history_store.add_message(event.unified_msg_origin, msg)

    @filter.on_llm_request(priority=-10)
    async def on_req_inject_context(self, event, req):
        """在 LLM 请求前注入场景 XML 和原始消息文本"""
        if not self._context_enable:
            return
        umo = event.unified_msg_origin
        if not self._history_store.has_session(umo):
            return
        if not self._ensure_scene_engine(event):
            return

        records, state = await self._history_store.get_snapshot(umo)
        if not records:
            return

        current = records[-1]
        trigger_type, trigger_desc = self._scene_engine.detect_trigger(event, current)
        self._scene_engine.infer_addressee(
            current,
            records,
            bot_replied_to=state.bot_last_replied_to,
        )

        # 注入场景 XML
        scene_xml = self._scene_engine.build_scene_xml(
            trigger_type,
            trigger_desc,
            current,
            records,
            state.bot_last_spoke_at,
        )
        self._prompt_builder.inject_scene(req, scene_xml)

        # 注入原始消息文本到 req.prompt
        text = self._prompt_builder.build_text_prompt(records)
        self._prompt_builder.inject_text_prompt(req, text)

    @filter.on_llm_request(priority=-10000)
    async def on_req_clear_prompt(self, event, req):
        """清空 req.prompt，防止框架重复注入"""
        if not self._context_enable:
            return
        if event.get_message_type().value == "group":
            self._prompt_builder.clear_prompt(req)

    @filter.on_llm_response()
    async def on_response_record_bot(self, event, resp):
        """记录 Bot 回复，更新状态"""
        if not self._context_enable:
            return
        if not resp.completion_text:
            return
        if not self._ensure_scene_engine(event):
            return

        umo = event.unified_msg_origin
        sender_id = event.get_sender_id()
        sender_name = event.get_sender_name() or sender_id

        msg = MessageRecord(
            msg_id=f"bot_{id(resp)}",
            sender_id=self._scene_engine.bot_id,
            sender_name="[你]",
            content=resp.completion_text[:200],
            timestamp=time.time(),
            is_bot=True,
            talking_to=sender_id,
            talking_to_name=sender_name,
        )
        await self._history_store.add_message(umo, msg)
        await self._history_store.record_bot_response(
            umo,
            resp.completion_text,
            time.time(),
            replied_to=sender_id,
            replied_to_name=sender_name,
        )

    async def terminate(self):
        """
        可选择性实现异步的插件销毁方法，当插件被卸载/停用时会调用。
        """
        await self.curfew.stop_all_tasks()
        await self.db.close()
        logger.info("插件 astrbot_plugin_QQAdmin 已优雅关闭")
