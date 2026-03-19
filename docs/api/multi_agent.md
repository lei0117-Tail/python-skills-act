# MultiAgent API Reference

## Classes

### MultiAgent

主编排器，负责 Skill 识别和 SubAgent 委托。

#### 构造函数

```python
MultiAgent(
    provider: LLMProvider,
    tool_registry: ToolRegistry,
    skills_loader: SkillsLoader,
    workspace: Path,
    model: str = "glm-5",
    max_iterations: int = 30,
    enable_subagent: bool = True,
    max_concurrent_subagents: int = 3,
    enable_skill_cache: bool = True,
    cache_ttl: int = 300,
)
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | `LLMProvider` | 必填 | LLM 提供者 |
| `tool_registry` | `ToolRegistry` | 必填 | 工具注册中心 |
| `skills_loader` | `SkillsLoader` | 必填 | Skill 加载器 |
| `workspace` | `Path` | 必填 | 工作目录 |
| `model` | `str` | `"glm-5"` | 模型名称 |
| `max_iterations` | `int` | `30` | 主 Agent 最大迭代次数 |
| `enable_subagent` | `bool` | `True` | 是否启用 SubAgent 委托 |
| `max_concurrent_subagents` | `int` | `3` | 最大并发 SubAgent 数量 |
| `enable_skill_cache` | `bool` | `True` | 是否启用 Skill 识别缓存 |
| `cache_ttl` | `int` | `300` | 缓存过期时间(秒) |

#### 方法

##### `async run(user_message: str) -> tuple[str, list[str]]`

执行用户查询。

**参数:**
- `user_message` (str): 用户查询

**返回:**
- `tuple[str, list[str]]`: (响应文本, 使用的工具列表)

**示例:**
```python
response, tools = await multi_agent.run("北京今天天气怎么样?")
print(f"Response: {response}")
print(f"Tools used: {tools}")
```

##### `reset_history() -> None`

清空对话历史。

**示例:**
```python
multi_agent.reset_history()
```

##### `get_stats() -> dict[str, Any]`

获取统计信息。

**返回:**
```python
{
    "history_length": int,          # 历史记录长度
    "available_skills": int,        # 可用 Skill 数量
    "subagent_enabled": bool,       # SubAgent 是否启用
    "cache_enabled": bool,          # 缓存是否启用
    "cache_size": int,              # 缓存大小
    "total_tokens_used": int,       # 总 Token 使用量
    "tokens_saved": int,            # 节省的 Token 数量
}
```

**示例:**
```python
stats = multi_agent.get_stats()
print(f"Token 节省: {stats['tokens_saved']}")
```

##### `get_token_stats() -> dict[str, Any]`

获取详细的 Token 使用统计。

**返回:**
```python
{
    "total_tokens_used": int,       # 总使用量
    "tokens_saved": int,            # 节省量
    "savings_rate": float,          # 节省率 (0.0-1.0)
    "estimated_cost_saved": float,  # 估算节省成本
}
```

**示例:**
```python
token_stats = multi_agent.get_token_stats()
print(f"节省率: {token_stats['savings_rate']:.2%}")
print(f"节省成本: ${token_stats['estimated_cost_saved']:.4f}")
```

##### `clear_cache() -> None`

清空 Skill 识别缓存。

**示例:**
```python
multi_agent.clear_cache()
```

---

### SubAgent

轻量级执行器，负责单个 Skill 的隔离执行。

#### 构造函数

```python
SubAgent(
    provider: LLMProvider,
    tool_registry: ToolRegistry,
    execution_context: SkillExecutionContext,
)
```

**参数:**
- `provider` (LLMProvider): LLM 提供者
- `tool_registry` (ToolRegistry): 工具注册中心
- `execution_context` (SkillExecutionContext): 执行上下文

#### 方法

##### `async execute() -> SubAgentResult`

执行 Skill 并返回结果。

**返回:**
- `SubAgentResult`: 执行结果

---

### SubAgentResult

SubAgent 执行结果封装。

#### 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill_name` | `str` | Skill 名称 |
| `success` | `bool` | 是否成功 |
| `content` | `str` | 响应内容 |
| `tools_used` | `list[str]` | 使用的工具列表 |
| `error` | `str \| None` | 错误信息 |
| `token_usage` | `dict[str, int]` | Token 使用统计 |

**示例:**
```python
result = await subagent.execute()
if result.success:
    print(f"Success: {result.content}")
    print(f"Tools used: {result.tools_used}")
else:
    print(f"Error: {result.error}")
```

---

### SkillExecutionContext

Skill 执行上下文配置。

#### 字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skill_name` | `str` | 必填 | Skill 名称 |
| `skill_content` | `str` | 必填 | Skill 内容 |
| `user_query` | `str` | 必填 | 用户查询 |
| `workspace` | `Path` | 必填 | 工作目录 |
| `model` | `str` | 必填 | 模型名称 |
| `max_iterations` | `int` | `10` | 最大迭代次数 |

---

## Factory Functions

### `build_multi_agent(...) -> MultiAgent`

构建 MultiAgent 实例的工厂函数。

```python
def build_multi_agent(
    provider: LLMProvider,
    tool_registry: ToolRegistry,
    skills_loader: SkillsLoader,
    workspace: Path,
    model: str = "glm-5",
    max_iterations: int = 30,
    enable_subagent: bool = True,
    max_concurrent_subagents: int = 3,
    enable_skill_cache: bool = True,
    cache_ttl: int = 300,
) -> MultiAgent
```

**示例:**
```python
from skills_executor.agent.multi_agent import build_multi_agent

multi_agent = build_multi_agent(
    provider=CustomProvider(),
    tool_registry=registry,
    skills_loader=SkillsLoader("~/.claude/skills"),
    workspace=Path.cwd(),
    model="glm-5",
    enable_subagent=True,
    enable_skill_cache=True,
)
```

---

## Security

### SecurityValidator

安全验证和清理工具。

#### 类方法

##### `sanitize_user_input(user_message: str, max_length: int = 5000) -> str`

清理用户输入，防止提示词注入。

**参数:**
- `user_message` (str): 原始用户输入
- `max_length` (int): 最大长度限制

**返回:**
- `str`: 清理后的输入

**功能:**
- 移除 XML/HTML 标签
- 限制长度
- 检测恶意模式

##### `validate_command(command: str) -> tuple[bool, str | None]`

验证 Shell 命令的安全性。

**参数:**
- `command` (str): 要验证的命令

**返回:**
- `tuple[bool, str | None]`: (是否安全, 错误信息)

**阻止的危险命令:**
- `rm -rf`
- `sudo rm`
- `chmod +x`
- `mkfs`
- `dd if=`
- Fork bomb

##### `redact_sensitive_info(content: str) -> str`

脱敏处理敏感信息。

**参数:**
- `content` (str): 原始内容

**返回:**
- `str`: 脱敏后的内容

**处理的信息类型:**
- API keys (32+ 字符)
- IP 地址
- 邮箱地址
- 密码

---

## Usage Examples

### 基本使用

```python
import asyncio
from pathlib import Path
from skills_executor.agent.multi_agent import build_multi_agent
from skills_executor.providers.custom_provider import CustomProvider
from skills_executor.skills.SkillsLoader import SkillsLoader
from skills_executor.tools.registry import ToolRegistry

async def main():
    # 创建 MultiAgent
    multi_agent = build_multi_agent(
        provider=CustomProvider(),
        tool_registry=ToolRegistry(),
        skills_loader=SkillsLoader("~/.claude/skills"),
        workspace=Path.cwd(),
    )

    # 执行查询
    response, tools = await multi_agent.run("北京天气")
    print(f"Response: {response}")

    # 查看统计
    stats = multi_agent.get_stats()
    print(f"Stats: {stats}")

asyncio.run(main())
```

### 禁用 SubAgent

```python
multi_agent = build_multi_agent(
    ...,
    enable_subagent=False,  # 禁用 SubAgent
)
```

### 自定义配置

```python
multi_agent = build_multi_agent(
    ...,
    max_concurrent_subagents=5,  # 增加并发数
    enable_skill_cache=True,     # 启用缓存
    cache_ttl=600,               # 10 分钟缓存
)
```

### Token 统计

```python
# 执行多次查询
await multi_agent.run("query 1")
await multi_agent.run("query 2")
await multi_agent.run("query 3")

# 查看 Token 统计
token_stats = multi_agent.get_token_stats()
print(f"总使用: {token_stats['total_tokens_used']}")
print(f"节省: {token_stats['tokens_saved']}")
print(f"节省率: {token_stats['savings_rate']:.2%}")
```

---

## Performance Tips

### 1. 启用缓存

```python
multi_agent = build_multi_agent(
    ...,
    enable_skill_cache=True,  # 节省 200ms + 500 tokens
)
```

### 2. 调整并发数

```python
# 高负载场景
multi_agent = build_multi_agent(
    ...,
    max_concurrent_subagents=5,
)

# 低资源场景
multi_agent = build_multi_agent(
    ...,
    max_concurrent_subagents=1,
)
```

### 3. 定期清理缓存

```python
# 在长时间运行的应用中
if multi_agent.get_stats()["cache_size"] > 100:
    multi_agent.clear_cache()
```

---

## Error Handling

### SubAgent 失败回退

```python
# MultiAgent 自动回退到主 Agent
response, tools = await multi_agent.run("query")

# 检查是否使用了 SubAgent
if "Skill:" in response:
    print("Used SubAgent")
else:
    print("Used main agent (fallback)")
```

### 异常处理

```python
try:
    response, tools = await multi_agent.run("query")
except Exception as e:
    logger.error(f"MultiAgent error: {e}")
    # 回退到简单 Agent
    agent = build_default_agent(...)
    response, tools = await agent.run("query")
```
