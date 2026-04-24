# QQ端百宝箱

> 本项目基于 [astrbot_plugin_qqadmin](https://github.com/Zhalslar/astrbot_plugin_qqadmin) 由AI重构。

为LLM提供QQ群管工具接口的AstrBot插件，支持禁言、解禁、改名、头衔、精华、搜索历史等，并具备上下文感知能力让LLM理解对话场景。

## 功能概览

### LLM可调用工具

#### 信息查询
| 工具名 | 说明 |
|--------|------|
| `get_group_member_list` | 获取当前群的所有成员列表（昵称/名片/QQ/身份/头衔） |
| `get_group_info` | 获取群信息（群号/群名/人数/描述/创建时间） |
| `get_user_info` | 查询用户资料（群聊优先群名片，私聊取陌生人信息） |

#### 群管操作
| 工具名 | 说明 |
|--------|------|
| `poke_user` | 戳一戳指定用户（群聊/私聊自动判断） |
| `set_group_ban` | 禁言用户（支持0秒解禁，自动权限检查） |
| `cancel_group_ban` | 解除禁言 |
| `set_group_card` | 修改用户群名片 |
| `set_group_special_title` | 设置用户群头衔 |
| `set_essence_msg` | 将消息设为精华 |

#### 搜索工具
| 工具名 | 说明 |
|--------|------|
| `search_group_history` | 搜索当前群聊历史记录 |
| `search_other_chats` | 跨群/私聊搜索 |
| `get_scene_info` | 获取当前对话场景判断结果 |

#### 批量操作
| 工具名 | 说明 |
|--------|------|
| `batch_ban` | 批量禁言 |
| `batch_set_card` | 批量修改群名片 |
| `batch_send_msg` | 批量向多个群发消息 |

#### 自动监控
- **刷屏检测**：自动检测并禁言刷屏用户
- **进群审核**：监听进群/退群事件，支持欢迎词、临时禁言、拉黑

## 配置说明

### 基础设置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `divided_manage` | bool | `true` | 分群管理，开启后每个群有独立配置 |
| `admin_audit` | bool | `true` | 进群申请发送给管理员审批 |

### 上下文感知

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `context_enable` | bool | `true` | 启用上下文感知（让LLM理解对话场景） |
| `context_max_history` | int | `50` | 每个群缓存的消息条数上限 |
| `context_max_sessions` | int | `100` | 上下文缓存的最大会话数（LRU淘汰） |
| `context_inject_count` | int | `8` | 注入LLM的历史消息条数 |
| `context_max_chars` | int | `2000` | 历史消息最大字符数（防token溢出） |
| `bot_names` | list | `[]` | Bot昵称列表（用于检测是否被@） |
| `llm_get_msg_count` | int | `10` | LLM工具调用时传入的历史消息上限 |

### 消息处理

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `forward_parse_enable` | bool | `true` | 启用合并转发消息解析 |
| `forward_max_nesting_depth` | int | `3` | 合并转发最大嵌套层数 |
| `forward_include_sender_info` | bool | `true` | 转发消息附带发送者昵称 |
| `forward_include_timestamp` | bool | `true` | 转发消息附带发送时间 |

### LLM工具开关

| 配置项 | 说明 |
|--------|------|
| `tool_group_info` | 信息查询工具（成员列表/群信息/用户信息） |
| `tool_group_action` | 群管操作工具（戳一戳/禁言/改名/头衔/精华） |
| `tool_group_search` | 搜索工具（历史记录/跨群搜索/场景判断） |
| `tool_group_batch` | 批量操作工具（批量禁言/改名片/发消息） |
| `tool_group_monitor` | 自动监控（刷屏检测/进群审核） |

## 权限说明

LLM工具遵循以下权限规则：
- **信息查询**：所有群成员可用
- **群管操作**：需Bot具有相应权限（管理员/群主）
- **批量操作**：需管理员权限
- **自动监控**：需管理员权限

## 使用示例

### LLM调用示例

```
用户：帮我看看现在群里谁在线
LLM调用：get_group_member_list → 获取成员列表后回答
```

```
用户：禁言一下@小明，5分钟
LLM调用：set_group_ban(user_id="小明QQ", duration=300) → 执行禁言
```

```
用户：查找一下之前谁提到了项目计划
LLM调用：search_group_history(keyword="项目计划") → 返回匹配消息
```

## 环境要求

- AstrBot v3.0.0+
- 适配平台：aiocqhttp（OneBot V11）
- Bot需具有：管理员或群主权限（部分功能）
