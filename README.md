<div align="center">

# OpenRouter Model Search

[![Alfred 5](https://img.shields.io/badge/Alfred-5-purple?logo=alfred)](https://www.alfredapp.com/)
[![Python 3](https://img.shields.io/badge/Python-3.8+-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Check](https://github.com/chenjh16/openrouter-search-workflow/actions/workflows/check.yml/badge.svg)](https://github.com/chenjh16/openrouter-search-workflow/actions/workflows/check.yml)
[![Release](https://github.com/chenjh16/openrouter-search-workflow/actions/workflows/release.yml/badge.svg)](https://github.com/chenjh16/openrouter-search-workflow/actions/workflows/release.yml)

**[English](#english) | [中文](#中文)**

</div>

---

<a id="english"></a>

## English

An Alfred Workflow for searching and inspecting AI models on [OpenRouter](https://openrouter.ai).

### Features

- 🔍 **Quick Model Search** — Search through hundreds of AI models available on OpenRouter
- 📊 **Provider Details** — View detailed pricing, latency, and throughput for each provider
- 🔗 **Quick Navigation** — Open model pages, HuggingFace, or ModelScope links directly
- 🖼️ **Provider Icons** — Automatic icon fetching for visual identification
- 💾 **Smart Caching** — Configurable cache for fast, responsive searches
- 🧹 **Cache Management** — Built-in command to clear all cached data
- 🆕 **New Model Labeling** — Highlights models released within the last 14 days
- 🔄 **Force Refresh** — Manually trigger a full update of models

### Installation

1. Download the latest `OpenRouter.alfredworkflow` from the [Releases](https://github.com/chenjh16/openrouter-search-workflow/releases) page
2. Double-click the file to install it in Alfred
3. That's it! (See [Configuration](#configuration) for optional API Key setup)

#### Requirements

- [Alfred 5](https://www.alfredapp.com/) with Powerpack license
- Python 3.8+ (pre-installed on macOS)

### Usage

#### Search Models

Type `or` followed by your search query:

```
or kimi
or gpt-4
or claude
```

Each result displays:

- **Model name** with capability icons (👁️ Vision, 🛠️ Tools, 🎯 JSON, 🧠 Reasoning)
- **Modality** — Input/Output types (e.g., `[T+I→T]` for text+image to text)
- **Context length** — Maximum tokens the model supports
- **Pricing** — Input/Output cost per million tokens

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| <kbd>⏎</kbd> | Open model page on OpenRouter |
| <kbd>⇥</kbd> | View provider details |
| <kbd>⌥⏎</kbd> | Copy model ID (Copy Model ID in search; Copy URL on Header/HuggingFace/ModelScope items; Copy Provider Tag on provider items) |
| <kbd>⌃⏎</kbd> | Copy curl test command (General command on search/header; Provider-specific on provider items) |

#### View Provider Details

Press <kbd>Tab</kbd> on a search result to view detailed provider information:

```
or >moonshotai/kimi-k2.5
```

The detail view shows:

- Model name and description
- HuggingFace / ModelScope links (if available)
- **Provider list** with latency, throughput, context length, and pricing

#### Clear Cache

Type `orc` to clear all cached data (models, endpoints, icons):

```
orc
```

#### Force Refresh

Type `orf` to force a refresh of all cached data (models, icons, endpoints).

```
orf
```

### Configuration

Configure through Alfred Workflow settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | API key for latency/throughput data | — |
| `MODELS_TTL` | Models cache duration (minutes) | 1440 (24h) |
| `ENDPOINTS_TTL` | Endpoints cache duration (minutes) | 30 |
| `ICONS_TTL` | Icons cache duration (minutes) | 43200 (30d) |

> **Note**: Get your API key from [openrouter.ai/keys](https://openrouter.ai/keys). Latency and throughput data requires authentication.

### Development

```bash
# Clone the repository
git clone https://github.com/chenjh16/openrouter-search-workflow.git
cd openrouter-search-workflow

# Build and install the workflow
make

# Install development dependencies
make install-dev

# Run code quality checks (pylint, mypy, ruff)
make check

# Clean build artifacts and cache
make clean
```

#### Project Structure

```
├── main.py             # Main entry point (search, detail, cache clear)
├── download_icon.py    # Background icon downloader
├── workflow/           # Workflow package
│   ├── config.py       # Configuration
│   ├── alfred.py       # Alfred item generation
│   ├── api.py          # API client
│   ├── cache.py        # Cache management
│   ├── icons.py        # Icon management
│   ├── utils.py        # Utilities (formatter)
│   └── commands.py     # Core command logic
├── info.plist          # Alfred workflow configuration
├── icon.png            # Workflow icon
├── resources/          # Provider SVG icons
├── pyproject.toml      # Project configuration and dependencies
└── Makefile            # Build and check commands
```

### License

MIT License

---

<a id="中文"></a>

## 中文

一个用于在 [OpenRouter](https://openrouter.ai) 上搜索和查看 AI 模型的 Alfred Workflow。

### 功能特性

- 🔍 **快速搜索模型** — 搜索 OpenRouter 上数百个可用的 AI 模型
- 📊 **Provider 详情** — 查看每个供应商的定价、延迟和吞吐量
- 🔗 **快捷导航** — 直接从 Alfred 打开模型页面、HuggingFace 或 ModelScope 链接
- 🖼️ **Provider 图标** — 自动获取供应商图标以便识别
- 💾 **智能缓存** — 可配置缓存时间，确保快速响应
- 🧹 **缓存管理** — 内置命令清除所有缓存数据
- 🆕 **新模型标注** — 高亮显示过去 14 天内发布的模型
- 🔄 **强制刷新** — 手动触发模型全量更新

### 安装

1. 从 [Releases](https://github.com/chenjh16/openrouter-search-workflow/releases) 页面下载最新的 `OpenRouter.alfredworkflow`
2. 双击文件即可安装到 Alfred
3. 完成！（可选 [配置](#配置) API Key 以获取完整数据）

#### 系统要求

- [Alfred 5](https://www.alfredapp.com/) 及 Powerpack 许可证
- Python 3.8+（macOS 预装）

### 使用方法

#### 搜索模型

输入 `or` 加上搜索关键词：

```
or kimi
or gpt-4
or claude
```

每个结果显示：

- **模型名称**及能力图标（👁️ 视觉、🛠️ 工具、🎯 JSON、🧠 推理）
- **模态** — 输入/输出类型（如 `[T+I→T]` 表示文本+图像到文本）
- **上下文长度** — 模型支持的最大 token 数
- **定价** — 每百万 token 的输入/输出费用

**快捷键：**

| 按键 | 操作 |
|-----|------|
| <kbd>⏎</kbd> | 打开 OpenRouter 模型页面 |
| <kbd>⇥</kbd> | 查看供应商详情 |
| <kbd>⌥⏎</kbd> | 复制模型 ID（列表页为复制模型 ID；详情页 顶部/HuggingFace/ModelScope 条目上为复制链接；供应商条目上为复制 Provider Tag） |
| <kbd>⌃⏎</kbd> | 复制 curl 测试命令（列表页/详情页顶部复制通用命令；供应商条目复制指定供应商命令） |

#### 查看供应商详情

在搜索结果上按 <kbd>Tab</kbd> 查看供应商详情：

```
or >moonshotai/kimi-k2.5
```

详情视图显示：

- 模型名称和描述
- HuggingFace / ModelScope 链接（如有）
- **供应商列表**：延迟、吞吐量、上下文长度和定价

#### 清除缓存

输入 `orc` 清除所有缓存数据（模型、端点、图标）：

```
orc
```

#### 强制刷新

输入 `orf` 强制刷新所有缓存数据（模型、图标、端点）：

```
orf
```

### 配置

通过 Alfred Workflow 设置进行配置：

| 变量 | 描述 | 默认值 |
|-----|------|-------|
| `OPENROUTER_API_KEY` | 用于获取延迟/吞吐量数据的 API 密钥 | — |
| `MODELS_TTL` | 模型缓存时间（分钟） | 1440 (24h) |
| `ENDPOINTS_TTL` | 端点缓存时间（分钟） | 30 |
| `ICONS_TTL` | 图标缓存时间（分钟） | 43200 (30d) |

> **注意**：从 [openrouter.ai/keys](https://openrouter.ai/keys) 获取 API Key。延迟和吞吐量数据需要认证。

### 开发

```bash
# 克隆仓库
git clone https://github.com/chenjh16/openrouter-search-workflow.git
cd openrouter-search-workflow

# 构建并安装 workflow
make

# 安装开发依赖
make install-dev

# 运行代码质量检查 (pylint, mypy, ruff)
make check

# 清理构建产物和缓存
make clean
```

#### 项目结构

```
├── main.py             # 主入口脚本（搜索、详情、清除缓存）
├── download_icon.py    # 后台图标下载器
├── workflow/           # Workflow 核心包
│   ├── config.py       # 配置
│   ├── alfred.py       # Alfred 条目生成
│   ├── api.py          # API 客户端
│   ├── cache.py        # 缓存管理
│   ├── icons.py        # 图标管理
│   ├── utils.py        # 工具类 (格式化)
│   └── commands.py     # 核心命令逻辑
├── info.plist          # Alfred workflow 配置
├── icon.png            # Workflow 图标
├── resources/          # Provider SVG 图标
├── pyproject.toml      # 项目配置和依赖
└── Makefile            # 构建命令
```

### 许可证

MIT License
