# 售后多智能体 (Multi-Agent)

基于 FastAPI + OpenAI Agents SDK 构建的多智能体系统，提供智能问答、意图识别、任务分发等能力。

## 项目结构

```
its_multi_agent/
├── backend/
│   ├── app/                    # 主后端服务
│   │   ├── api/               # API 路由层
│   │   ├── config/            # 配置管理
│   │   ├── infrastructure/    # 基础设施层
│   │   │   ├── ai/           # AI 模型客户端
│   │   │   ├── database/     # MySQL 连接池
│   │   │   ├── logging/      # 日志管理
│   │   │   └── tools/        # 工具集成 (MCP)
│   │   ├── multi_agent/       # 智能体层
│   │   │   ├── orchestrator_agent.py   # 主调度智能体
│   │   │   ├── technical_agent.py      # 技术专家智能体
│   │   │   └── service_agent.py        # 服务站查询智能体
│   │   ├── prompts/           # 智能体提示词模板
│   │   ├── repositories/       # 数据访问层
│   │   ├── schemas/           # Pydantic 数据模型
│   │   ├── services/          # 业务服务层
│   │   └── tests/             # 单元测试
│   └── knowledge/             # 知识库服务
│       ├── agents/            # Agent 配置
│       ├── api/               # 知识库 API
│       ├── cli/               # 命令行工具
│       ├── config/            # 配置
│       ├── data/              # 知识数据
│       └── repositories/     # 向量存储
└── front/
    ├── agent_web_ui/          # 主前端 (Vue3)
    └── knowlege_platform_ui/ # 知识平台前端
```

## 技术栈

### 后端
- **框架**: FastAPI + Uvicorn
- **AI**: OpenAI Agents SDK
- **数据库**: MySQL + Chroma (向量数据库)
- **协议**: MCP (Model Context Protocol)

### 前端
- **框架**: Vue 3
- **UI**: Element Plus
- **构建**: Vite

## 功能特性

- **意图理解与任务分发** - 主调度智能体解析用户意图，智能路由到对应专业智能体
- **技术专家咨询** - 技术专家智能体提供专业代码和技术问题解答
- **服务站查询** - 服务站智能体支持地理位置查询、服务站检索等功能
- **知识库检索** - 本地知识库集成，快速检索维修知识
- **流式响应** - 支持 SSE 流式输出，实时返回处理进度
- **Human-in-the-Loop** - 敏感操作人工审批机制
- **MCP 工具集成** - 支持搜索、百度地图等多种外部工具

## 快速开始

### 环境要求

- Python 3.8+
- Node.js 16+
- MySQL 5.7+（可选，用于会话存储）

### 后端安装

```bash
cd backend/app
pip install -r requirements.txt
```

### 配置环境变量

创建 `backend/app/.env` 文件：

```bash
# 方案一：硅基流动
SF_API_KEY=your_sf_api_key
SF_BASE_URL=https://api.example.com

# 方案二：阿里百炼
AL_BAILIAN_API_KEY=your_bailian_api_key
AL_BAILIAN_BASE_URL=https://dashscope.aliyuncs.com
```

### 启动后端服务

```bash
cd backend/app
python api/main.py
# 或
uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8000
```

### 前端安装

```bash
cd front/agent_web_ui
npm install
npm run dev
```

## Docker 部署

### 环境要求

- Docker
- Docker Compose

### 快速启动

1. 复制环境变量配置文件：
```bash
cp .env.docker .env
# 编辑 .env 填入你的 API Key 等配置
```

2. 启动所有服务：
```bash
docker-compose up -d
```

3. 访问服务：
- 前端：http://localhost
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 停止服务

```bash
docker-compose down
```

### 查看日志

```bash
docker-compose logs -f
```

## License

MIT License
