# QQ端百宝箱

[![Version](https://img.shields.io/badge/version-v1.3.0-blue.svg)](https://github.com/OMSociety/astrbot_plugin_qqassistant)
[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A5v4-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

为 LLM 提供 QQ 群管工具接口的 AstrBot 插件，支持禁言、解禁、改名、头衔、精华、历史搜索、批量操作等，具备上下文感知能力让 LLM 理解对话场景。

> 本项目由AI编写，部分源码基于 [astrbot_plugin_qqadmin](https://github.com/Zhalslar/astrbot_plugin_qqadmin) 。

[快速开始](#-快速开始) • [功能列表](#-功能列表) • [配置项](#-配置项说明) • [LLM 工具](#-llm-可调用工具) • [更新日志](CHANGELOG.md)

---

## 📖 功能概览

### 核心能力
- **信息查询** — 群成员列表、用户资料、群信息，LLM 可主动获取对话上下文
- **群管操作** — 禁言/解禁、戳一戳、改名片、设头衔、设精华，一套全包
- **搜索工具** — 群聊历史搜索、跨群/私聊搜索、场景感知，让 LLM 拥有记忆力
- **批量操作** — 批量禁言、批量改名片、批量发消息，管理效率拉满
- **自动监控** — 刷屏自动检测禁言、进群审核欢迎，解放双手

### 智能上下文
- 🧠 **对话感知** — 自动缓存群聊消息，向 LLM 注入历史上下文，让回复不再「失忆」
- 📨 **合并转发解析** — 自动展开多层嵌套转发消息，还原完整对话链
- 🔍 **被 @ 检测** — 自动识别 Bot 是否被 @，精准应对点名提问

---

## 🚀 快速开始

### 安装

**方式一：插件市场**
- AstrBot WebUI → 插件市场 → 搜索 `astrbot_plugin_qqassistant`

**方式二：GitHub 仓库**
- AstrBot WebUI → 插件管理 → ＋ 安装
- 粘贴仓库地址：`https://github.com/OMSociety/astrbot_plugin_qqassistant`

### 依赖安装
```bash
pip install -r requirements.txt
```
核心依赖：无额外依赖，基于 AstrBot 内置 SDK。

---

## 📋 功能列表

### 信息查询

| 工具名 | 说明 |
|:----|:----|
| `get_group_member_list` | 获取当前群所有成员列表（昵称/名片/QQ/身份/头衔） |
| `get_user_info` | 查询用户资料（群聊优先群名片，私聊取陌生人信息） |
| `get_group_info` | 获取群信息（群号/群名/人数/描述等） |

### 群管操作

| 工具名 | 说明 |
|:----|:----|
| `poke_user` | 戳一戳指定用户（群聊/私聊自动判断） |
| `set_group_ban` | 禁言用户（支持 0 秒解禁，自动权限检查） |
| `cancel_group_ban` | 解除禁言 |
| `set_group_card` | 修改用户群名片 |
| `set_group_special_title` | 设置用户群头衔 |
| `set_essence_msg` | 将消息设为精华 |

### 搜索工具

| 工具名 | 说明 |
|:----|:----|
| `search_group_history` | 搜索当前群聊历史记录 |
| `search_other_chats` | 跨群/私聊搜索 |
| `get_scene_info` | 获取当前对话场景判断结果 |

### 批量操作

| 工具名 | 说明 |
|:----|:----|
| `batch_ban` | 批量禁言 |
| `batch_set_card` | 批量修改群名片 |
| `batch_send_msg` | 批量向多个群发消息 |

---

## ⚙️ 配置项说明

### 基础设置

| 配置项 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `divided_manage` | bool | `true` | 分群管理，开启后每个群有独立配置 |
| `admin_audit` | bool | `true` | 进群申请发送给管理员审批 |

### 上下文感知

| 配置项 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `context_enable` | bool | `true` | 启用上下文感知（让 LLM 理解对话场景） |
| `context_max_history` | int | `50` | 每个群缓存的消息条数上限 |
| `context_max_sessions` | int | `100` | 上下文缓存的最大会话数（LRU 淘汰） |
| `context_inject_count` | int | `8` | 注入 LLM 的历史消息条数 |
| `context_max_chars` | int | `2000` | 历史消息最大字符数（防 token 溢出） |
| `bot_names` | list | `[]` | Bot 昵称列表（用于检测是否被 @） |
| `llm_get_msg_count` | int | `10` | LLM 工具调用时传入的历史消息上限 |

### 消息处理

| 配置项 | 类型 | 默认值 | 说明 |
|:----|:----|:----|:----|
| `forward_parse_enable` | bool | `true` | 启用合并转发消息解析 |
| `forward_max_nesting_depth` | int | `3` | 合并转发最大嵌套层数 |
| `forward_include_sender_info` | bool | `true` | 转发消息附带发送者昵称 |
| `forward_include_timestamp` | bool | `true` | 转发消息附带发送时间 |

### LLM 工具开关

| 配置项 | 说明 |
|:----|:----|
| `tool_group_info` | 信息查询工具（成员列表/群信息/用户信息） |
| `tool_group_action` | 群管操作工具（戳一戳/禁言/改名/头衔/精华） |
| `tool_group_search` | 搜索工具（历史记录/跨群搜索/场景判断） |
| `tool_group_batch` | 批量操作工具（批量禁言/改名片/发消息） |
| `tool_group_monitor` | 自动监控（刷屏检测/进群审核） |

---

## 🛠️ LLM 可调用工具

### 信息查询类

| 工具 | 参数 | 说明 |
|:----|:----|:----|
| `get_group_member_list` | 无 | 获取群成员列表 |
| `get_user_info` | `qq_id` (可选) | 查询用户资料 |
| `get_group_info` | 无 | 获取群详细信息 |

### 群管操作类

| 工具 | 参数 | 说明 |
|:----|:----|:----|
| `poke_user` | `qq_id` | 戳一戳用户 |
| `set_group_ban` | `user_id`, `duration`（秒，0=解禁） | 禁言用户 |
| `cancel_group_ban` | `user_id` | 解除禁言 |
| `set_group_card` | `user_id`, `card` | 修改群名片 |
| `set_group_special_title` | `user_id`, `title` | 设置群头衔 |
| `set_essence_msg` | `message_id` | 设精华消息 |

### 搜索类

| 工具 | 参数 | 说明 |
|:----|:----|:----|
| `search_group_history` | `keyword`, `count`（默认 10） | 搜索群聊历史 |
| `search_other_chats` | `is_group`, `subject_id`, `keyword` | 跨群/私聊搜索 |
| `get_scene_info` | 无 | 获取当前场景判断 |

### 批量操作类

| 工具 | 参数 | 说明 |
|:----|:----|:----|
| `batch_ban` | `user_ids` (list), `duration` | 批量禁言 |
| `batch_set_card` | `user_cards` (dict) | 批量改名片 |
| `batch_send_msg` | `group_ids` (list), `message` | 批量发消息 |

---

## 📝 使用示例

```
用户：帮我看看现在群里谁在线
LLM 调用：get_group_member_list → 获取成员列表后回答
```

```
用户：禁言一下 @小明，5 分钟
LLM 调用：set_group_ban(user_id="小明QQ", duration=300) → 执行禁言
```

```
用户：查找一下之前谁提到了项目计划
LLM 调用：search_group_history(keyword="项目计划") → 返回匹配消息
```

---

## 🔒 权限说明

LLM 工具遵循以下权限规则：

| 工具类别 | 权限要求 |
|:----|:----|
| 信息查询 | 所有群成员可用 |
| 群管操作 | Bot 需具有管理员/群主权限 |
| 批量操作 | 需管理员权限 |
| 自动监控 | 需管理员权限 |

---

## 📁 文件结构

```
astrbot_plugin_qqassistant/
├── main.py                    # 主逻辑、工具注册、自动监控
├── config.py                  # 配置管理
├── permission.py              # 权限检查工具
├── unified_context/           # 上下文感知模块
├── tools/                     # LLM 工具模块
│   ├── llm_tools.py           # 基础工具（查询/操作）
│   ├── llm_batch_tools.py     # 批量操作工具
│   └── llm_cross_tools.py     # 跨上下文搜索工具
├── core/                      # 核心功能模块
├── data.py                    # 数据处理
├── utils_pkg/                 # 工具包
├── _conf_schema.json          # 配置项 schema
├── metadata.yaml              # 插件元信息
├── README.md                  # 本文档
└── CHANGELOG.md               # 更新日志
```

---

## 🌐 环境要求

- **AstrBot** ≥ v4.0.0
- **适配平台**：aiocqhttp（OneBot V11）
- **Bot 权限**：管理员或群主（部分功能需要）

---

## 📝 更新日志

> 📋 **[查看完整更新日志 →](CHANGELOG.md)**

---

## 🤝 贡献与反馈

如遇问题请在 [GitHub Issues](https://github.com/OMSociety/astrbot_plugin_qqassistant/issues) 提交，欢迎 Pull Request！

---

## 📜 许可证

本项目采用 **MIT License** 开源协议。

---

## 👤 作者

**Slandre & Flandre** — [@OMSociety](https://github.com/OMSociety)
