# Skills Executor

一个基于 LLM 的智能代理执行框架，核心特色是支持 **Skill 技能系统**，通过加载 Markdown 格式的技能文件来扩展 AI 代理的能力。

> 参考: [nanobot](https://github.com/HKUDS/nanobot) - 本项目从 nanobot 中提取并独立封装了核心执行框架。

## 核心特性

- **🎯 Skills 技能系统**: 通过 Markdown 文件定义技能，动态加载和扩展 AI 能力
- **🔧 工具注册中心**: 支持动态注册工具，内置文件操作、Shell 执行等常用工具
- **🤖 Agent 循环**: 自动处理 LLM 与工具调用的交互循环
- **📡 多模型支持**: 支持 OpenAI 兼容 API（美团内部 GLM、GPT 等）
- **💻 CLI 命令行工具**: 开箱即用的命令行接口 `python-skill-bot`

## 安装

### 环境要求

- Python >= 3.11
- 推荐使用 `uv` 或 `pip` 进行安装

### 安装步骤

```bash
# 克隆项目
git clone <your-repo-url>
cd python-skills-act

# 创建虚拟环境（推荐）
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .

# 或使用 uv
uv pip install -e .
```

### 配置环境变量

在项目根目录创建 `.env` 文件：

```bash
# 复制模板
cp .env.example .env

# 编辑配置
vim .env
```

`.env` 文件内容：

```env
# LLM Provider Configuration
LLM_API_KEY=your-api-key-here
LLM_API_BASE=https://api.openai.com/v1
LLM_DEFAULT_MODEL=gpt-4o-mini
```

## 使用方式

### 1. 命令行工具 (CLI)

安装后可直接使用 `python-skill-bot` 命令：

```bash
# 基本用法
python-skill-bot run -m "你好"

# 查询天气
python-skill-bot run -m "北京今天天气怎么样？"

# 指定模型
python-skill-bot run -m "帮我写一段代码" --model gpt-4

# 指定工作目录
python-skill-bot run -m "列出当前目录文件" -w /path/to/workspace

# 开启详细日志
python-skill-bot run -m "你好" -v

# 查看版本
python-skill-bot version

# 查看帮助
python-skill-bot --help
```

### 2. Python API

```python
import asyncio
from pathlib import Path
from skills_executor.agent.agent import build_default_agent

async def main():
    # 使用默认配置创建 Agent
    agent = build_default_agent(
        skill_folder="~/.claude/skills",  # 技能目录
        workspace=Path.cwd(),              # 工作目录
        model="gpt-4o-mini",              # 模型名称
    )

    # 执行查询
    response, tools_used = await agent.run("帮我查询北京今天的天气")
    print(f"Response: {response}")
    print(f"Tools used: {tools_used}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Skills 技能系统

技能是 Markdown 格式的文件，通过 YAML frontmatter 定义元数据，正文描述具体操作指令。

### 技能文件结构

```
~/.claude/skills/
├── weather/
│   └── SKILL.md       # 天气查询技能
├── csv-analysis/
│   └── SKILL.md       # CSV 分析技能
└── code-review/
    └── SKILL.md       # 代码审查技能
```

### 技能文件示例

```markdown
---
name: weather
description: 获取当前天气和天气预报
always: false
metadata: |
  {"requires": {"bins": ["curl"]}}
---

# 天气查询技能

使用 curl 从 wttr.in 获取天气信息：

\`\`\`bash
curl -s "wttr.in/CITY?format=%l:+%c+%t"
\`\`\`

示例：
- 北京天气: `curl -s "wttr.in/Beijing?format=%l:+%c+%t"`
- 上海天气: `curl -s "wttr.in/Shanghai?format=%l:+%c+%t"`
```

### 元数据说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 技能名称 |
| `description` | string | 技能描述 |
| `always` | bool | 是否始终加载到上下文 |
| `metadata` | JSON | 额外配置，如依赖检查 |

## 内置工具

| 工具名 | 说明 |
|--------|------|
| `read_file` | 读取文件内容，支持分页 |
| `write_file` | 写入文件，自动创建目录 |
| `edit_file` | 编辑文件，支持模糊匹配替换 |
| `list_dir` | 列出目录内容，支持递归 |
| `exec` | 执行 Shell 命令 |

## 自定义工具

通过继承 `Tool` 基类创建自定义工具：

```python
from skills_executor.tools.base import Tool
from skills_executor.tools.registry import ToolRegistry

class CalculatorTool(Tool):
    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "执行数学计算"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"]
        }

    async def execute(self, expression: str) -> str:
        # 安全计算表达式
        import ast
        return str(ast.literal_eval(expression))

# 注册工具
registry = ToolRegistry()
registry.register(CalculatorTool())
```

## 项目结构

```
python-skills-act/
├── skills_executor/
│   ├── agent/           # Agent 核心逻辑
│   │   ├── agent.py     # Agent 类和工厂函数
│   │   └── context.py   # 上下文构建
│   ├── providers/       # LLM 提供者
│   │   ├── base.py      # 基类
│   │   └── custom_provider.py  # OpenAI 兼容实现
│   ├── skills/          # 技能系统
│   │   └── SkillsLoader.py
│   ├── tools/           # 工具实现
│   │   ├── base.py
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   └── registry.py
│   └── cli.py           # CLI 入口
├── .env.example         # 环境变量模板
├── pyproject.toml       # 项目配置
└── README.md
```

## 参考

- [nanobot](https://github.com/HKUDS/nanobot) - 原始项目，本项目从中提取核心框架

## License

MIT License
