# 更新日志

所有版本更新记录。

---

## v1.1.1

> 🔧 架构补线修复

### 架构与配置
- ✅ `main.py` 补上 `register_cross_tools(self)`，跨上下文搜索工具可正常注册
- ✅ 转发解析改为读取配置：`forward_parse_enable / forward_max_nesting_depth / forward_include_sender_info / forward_include_timestamp`
- ✅ `config.py` 兼容新旧键名：优先 `forward_parse_enable`，兼容 `enable_forward_message_parsing`
- ✅ `_conf_schema.json` 补齐 `context_max_sessions`，与运行时参数一致

### 工具行为
- ✅ 修复 `tools/llm_tools.py` 中工具开关判断写在 docstring 的问题，改为真实执行逻辑
- ✅ `tools/llm_cross_tools.py` 接入 `tool_group_search` 分组开关

### 清理
- 🧹 移除 `main.py` 未使用导入

---

## v1.1.0

> 🐛 修复版本 — 架构完备性修复 + 可维护性提升

### 正确性修复
- 🐛 `handle_spamming_ban_time` 写 `word_ban_time` 但 `spamming_ban` 读 `spamming_ban_time`，两把钥匙开一把锁（现已统一）
- ✨ 所有 LLM 工具接入分组开关（`tool_group_info/action/search/batch/monitor`），配置真正生效

### 资源与架构
- ✨ `on_unload` 新增外部会话资源关闭（Notion/HTTP 连接泄漏修复）
- 🗑️ 删除 `permission.py` 冗余的 `get_ats` 函数定义，统一使用 `utils.py` 版本
- 🗑️ 删除 `main.py` 中未使用的 `cross_tools_instance` 和 `ts` 变量

### Schema 完善
- ✅ 补齐 `_conf_schema.json` 默认配置字段（工具分组开关、上下文、历史记录、转发解析等），避免隐式关闭

---

## v1.0.0

> 🎉 初始版本

### 功能
- LLM工具：成员列表、群信息、用户信息查询
- LLM工具：戳一戳、禁言/解禁、改群名片、设置头衔、设置精华
- LLM工具：搜索群历史、跨群/私聊搜索、场景判断
- LLM工具：批量禁言、批量改名片、批量发消息
- 自动监控：刷屏检测禁言、进群审核事件监听
- 上下文感知：场景XML注入、历史消息缓存
- 合并转发消息解析
- 分群独立配置支持
