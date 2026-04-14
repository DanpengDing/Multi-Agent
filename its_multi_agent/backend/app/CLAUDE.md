# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

售后多智能体（Multi-Agent）智能问答后端服务，基于 FastAPI + OpenAI Agents SDK 构建的多智能体系统。

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python api/main.py
# 或
uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8000
```

## 核心架构

### 智能体层 (`multi_agent/`)
- `orchestrator_agent.py` - 主调度智能体，负责意图理解和任务分发
- `agent_factory.py` - 智能体工厂，创建 Agent 实例并绑定工具
- `technical_agent.py` - 技术专家智能体
- `service_agent.py` - 服务站查询智能体

### 服务层 (`services/`)
- `agent_service.py` - 多智能体协作核心逻辑，流式处理入口
- `hitl_service.py` - Human-in-the-Loop 审批服务，敏感操作需人工确认
- `session_service.py` - 会话历史管理
- `query_rewrite_service.py` - 查询改写，优化用户输入
- `structured_output_service.py` - 结构化输出解析

### API层 (`api/`)
- `routers.py` - API路由定义
  - `POST /api/query` - 流式执行智能体
  - `POST /api/human_approval` - 处理审批结果
  - `POST /api/user_sessions` - 获取用户会话列表

### 基础设施层 (`infrastructure/`)
- `ai/openai_client.py` - AI模型客户端（主模型/子模型）
- `tools/mcp/` - MCP工具集成（搜索、百度地图、知识库）
- `database/database_pool.py` - MySQL连接池
- `logging/logger.py` - 日志管理

### 提示词 (`prompts/`)
- `orchestrator_v1.md` - 主调度智能体指令
- `technical_agent.md` - 技术专家指令
- `comprehensive_service_agent.md` - 服务站智能体指令

## 配置

环境变量配置在 `.env` 文件，使用 `config/settings.py` 统一管理。必须配置以下之一：
- 硅基流动（SF_API_KEY + SF_BASE_URL）
- 阿里百炼（AL_BAILIAN_API_KEY + AL_BAILIAN_BASE_URL）

## 工具集成

智能体通过 MCP (Model Context Protocol) 调用外部工具：
- 搜索 MCP - 实时信息查询
- 百度地图 MCP - 地理位置、导航、服务站
- 本地知识库 MCP - 维修知识检索

## 开发规范

详见 `AGENTS.md`，核心规则：
- 所有新增/修改代码必须添加中文注释
- 涉及删除、核心逻辑变更、引入新依赖必须先询问用户
- 新功能开发需：需求澄清 → 方案设计 → 用户确认 → 编码实现
- 遵循最小侵入原则，优先复用现有代码结构