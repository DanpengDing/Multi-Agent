#  Multi-Agent 智能问答后端

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![OpenAI Agents SDK](https://img.shields.io/badge/OpenAI%20Agents%20SDK-1.0+-orange.svg)](https://platform.openai.com/docs/agents)

基于 FastAPI + OpenAI Agents SDK 构建的多智能体系统，提供智能问答、意图识别、任务分发等能力。

## 功能特性

- **意图理解与任务分发** - 主调度智能体解析用户意图，智能路由到对应专业智能体
- **技术专家咨询** - 技术专家智能体提供专业代码和技术问题解答
- **服务站查询** - 服务站智能体支持地理位置查询、服务站检索等功能
- **知识库检索** - 本地知识库集成，快速检索维修知识
- **流式响应** - 支持 SSE 流式输出，实时返回处理进度
- **Human-in-the-Loop** - 敏感操作人工审批机制
- **MCP 工具集成** - 支持搜索、百度地图等多种外部工具

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                         API 层                               │
│                    (FastAPI + Uvicorn)                       │
├─────────────────────────────────────────────────────────────┤
│                         服务层                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │ AgentService │ │  HITLService │ │ SessionService│         │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
├─────────────────────────────────────────────────────────────┤
│                        智能体层                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │  Orchestrator│ │   Technical  │ │   Service    │          │
│  │   Agent      │ │    Agent     │ │    Agent     │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
├─────────────────────────────────────────────────────────────┤
│                       基础设施层                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │  OpenAI      │ │     MCP      │ │  Database    │          │
│  │  Client      │ │    Servers   │ │    Pool      │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
app/
├── api/                    # API 路由层
│   └── main.py            # FastAPI 应用入口
├── config/                # 配置管理
│   └── settings.py        # 环境变量与配置项
├── infrastructure/        # 基础设施层
│   ├── ai/               # AI 模型客户端、提示词加载
│   ├── database/         # MySQL 连接池
│   ├── logging/          # 日志管理
│   └── tools/            # 工具集成（MCP、本地知识库）
├── multi_agent/           # 智能体层
│   ├── orchestrator_agent.py   # 主调度智能体
│   ├── technical_agent.py      # 技术专家智能体
│   └── service_agent.py        # 服务站查询智能体
├── prompts/              # 智能体提示词模板
├── repositories/          # 数据访问层
├── schemas/              # Pydantic 数据模型
├── services/             # 业务服务层
├── utils/                # 工具函数
├── tests/                # 单元测试
├── requirements.txt      # Python 依赖
└── .env                  # 环境变量配置示例
```

## 快速开始

### 环境要求

- Python 3.8+
- MySQL 5.7+（可选，用于会话存储）

### 安装依赖

```bash
cd app
pip install -r requirements.txt
```

### 配置环境变量

创建 `.env` 文件，配置以下必填项之一：

```bash
# 方案一：硅基流动
SF_API_KEY=your_sf_api_key
SF_BASE_URL=https://api.example.com

# 方案二：阿里百炼
AL_BAILIAN_API_KEY=your_bailian_api_key
AL_BAILIAN_BASE_URL=https://dashscope.aliyuncs.com
```

### 启动服务

```bash
# 方式一：直接运行
python api/main.py

# 方式二：使用 uvicorn
uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8000
```

服务启动后访问 `http://127.0.0.1:8000/docs` 查看 API 文档。

### 运行测试

```bash
python -m pytest tests/
```

## 配置说明

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `SF_API_KEY` | 是* | 硅基流动 API Key |
| `SF_BASE_URL` | 是* | 硅基流动 API 地址 |
| `AL_BAILIAN_API_KEY` | 是* | 阿里百炼 API Key |
| `AL_BAILIAN_BASE_URL` | 是* | 阿里百炼 API 地址 |
| `MYSQL_HOST` | 否 | MySQL 主机地址 |
| `MYSQL_PORT` | 否 | MySQL 端口 |
| `MYSQL_USER` | 否 | MySQL 用户名 |
| `MYSQL_PASSWORD` | 否 | MySQL 密码 |
| `MYSQL_DATABASE` | 否 | MySQL 数据库名 |

*注：至少需要配置硅基流动或阿里百炼之一

## License

MIT License
