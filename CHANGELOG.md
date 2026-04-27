# Changelog

> 本项目仍处于活跃维护中。

---

## [1.3.0] - 2026-04-27

### 🔧 工具规范化重构
- **FunctionTool 全面迁移**：所有 LLM 工具重构为 `FunctionTool` dataclass 方式，符合 AstrBot 官方规范
- **工具来源标识**：统一显示 `plugin` + `qqassistant`，名称为清晰的英文命名
- **批量工具开关**：`batch_ban`、`batch_set_card`、`batch_send_msg` 增加 `tool_group_batch` 开关检查
- **导出更新**：`tools/__init__.py` 同步更新工具类名

### 🐛 Bug 修复
- **嵌套转发解析**：修复合并转发消息多层嵌套时只解析到第一层的问题，现在支持完整递归展开（最高受 `forward_max_nesting_depth` 配置控制）
- **转发格式还原**：修复转发消息中时间戳格式与发送者信息的渲染逻辑，确保嵌套转发链完整呈现

---

## [1.2.0] - 2026-04-26

### 🔧 架构与配置
- **跨上下文工具注册**：`main.py` 补上 `register_cross_tools(self)`，跨群搜索工具可正常注册
- **转发解析配置化**：新增 `forward_parse_enable / forward_max_nesting_depth / forward_include_sender_info / forward_include_timestamp` 四项配置
- **配置键名兼容**：`config.py` 兼容新旧键名，优先读 `forward_parse_enable`，回退 `enable_forward_message_parsing`
- **Schema 补齐**：`_conf_schema.json` 补齐 `context_max_sessions`，与运行时参数一致

### 🐛 工具行为修复
- **开关逻辑修正**：修复 `tools/llm_tools.py` 中工具开关判断写在 docstring 的问题，改为真实执行逻辑
- **搜索工具开关**：`tools/llm_cross_tools.py` 接入 `tool_group_search` 分组开关

### 🧹 清理
- 移除 `main.py` 未使用导入

---

## [1.1.0] - 2026-04-25

### 🐛 正确性修复
- **刷屏检测配置**：修复 `handle_spamming_ban_time` 写 `word_ban_time` 但 `spamming_ban` 读 `spamming_ban_time` 的键名不一致问题
- **分组开关生效**：所有 LLM 工具接入分组开关（`tool_group_info/action/search/batch/monitor`），配置真正生效

### 🧹 资源与架构
- **资源释放**：`on_unload` 新增外部会话资源关闭
- **死代码清理**：删除 `permission.py` 冗余的 `get_ats` 函数定义，统一使用 `utils.py` 版本
- **变量清理**：删除 `main.py` 中未使用的 `cross_tools_instance` 和 `ts` 变量

### 📋 Schema 完善
- 补齐 `_conf_schema.json` 默认配置字段，避免隐式关闭
