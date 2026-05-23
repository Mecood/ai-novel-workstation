---
name: ai-novel-workstation
version: 1.0.0
description: "AI 小说创作工作站 - 开发流程 Skill"
category: dev
---

# AI 小说创作工作站 - 开发流程

## 触发条件

- 用户要求开发 AI 小说创作工作站
- 需要从零搭建 React + FastAPI 全栈项目
- 需要配置向量检索、一致性检查等 AI 功能

## 项目信息

| 维度 | 说明 |
|---|---|
| 项目路径 | `/Users/products/code/ai-novel-workstation` |
| 前端 | React 18 + TypeScript + Ant Design（清新素雅风格） |
| 后端 | FastAPI (Python) |
| 数据库 | PostgreSQL |
| 向量库 | ChromaDB |
| Embedding | BAAI/bge-m3（硅基流动 API） |
| Reranker | BAAI/bge-reranker-v2-m3（V2 阶段） |
| 部署 | Docker Compose |

## 开发步骤

### 阶段 1：项目框架搭建（第 1 周）

1. **前端框架初始化**
   ```bash
   cd /Users/products/code/ai-novel-workstation/frontend
   npm create vite@latest . -- --template react-ts
   npm install antd @ant-design/icons axios
   ```

2. **后端框架初始化**
   ```bash
   cd /Users/products/code/ai-novel-workstation/backend
   python -m venv venv
   source venv/bin/activate
   pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic python-dotenv
   ```

3. **Docker 配置**
   - 创建 `docker-compose.yml`
   - 创建 `Dockerfile`（前端 + 后端）
   - 创建 `.env.example`

4. **项目管理 CRUD**
   - 后端：项目创建/列表/详情/删除 API
   - 前端：项目列表页、详情页

5. **前后端联调**
   - 配置 CORS
   - 测试 API 连通性

### 阶段 2：AI 引擎集成（第 2 周）

1. **AI API 配置**
   - 硅基流动 API（Embedding + LLM）
   - DeepSeek API（章节生成）
   - 统一 AI 客户端封装

2. **故事核心生成**
   - Prompt 模板：`prompts/story_core.yaml`
   - API：`POST /api/v1/projects/{id}/story-core/generate`

3. **世界观生成**
   - Prompt 模板：`prompts/worldview.yaml`
   - API：`POST /api/v1/projects/{id}/worldview/generate`

4. **角色生成**
   - Prompt 模板：`prompts/character.yaml`
   - 状态追踪：`services/state_tracker.py`

### 阶段 3：章节创作 + 向量检索（第 3 周）

1. **向量检索引擎**
   - ChromaDB 初始化
   - Embedding 服务：`services/vector_search.py`
   - 切片策略：500-800 字/片

2. **章节生成**
   - Prompt 模板：`prompts/chapter.yaml`
   - SSE 流式输出
   - API：`POST /api/v1/projects/{id}/chapters/generate`

3. **前情提要**
   - 自动提取上一章节摘要
   - 向量检索最相关片段

### 阶段 4：一致性检查 + 伏笔管理（第 4 周）

1. **一致性检查器**
   - `services/consistency.py`
   - S1-S4 分级报告
   - API：`POST /api/v1/ai/check-consistency`

2. **伏笔管理**
   - 伏笔 CRUD
   - 状态追踪：planted / paid_off / abandoned
   - 未回收提醒

### 阶段 5：测试 + 优化 + 部署（第 5-6 周）

1. **功能测试**
   - 端到端测试
   - AI 生成质量评估

2. **性能优化**
   - SSE 流式输出优化
   - 向量检索缓存

3. **Docker 部署**
   - 一键启动：`docker-compose up -d`
   - 健康检查

## 目录结构

```
ai-novel-workstation/
├── frontend/                    # 前端
│   ├── src/
│   │   ├── components/          # 通用组件
│   │   ├── pages/               # 页面
│   │   ├── services/            # API 服务
│   │   ├── store/               # 状态管理
│   │   └── styles/              # 全局样式（清新素雅）
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                     # 后端
│   ├── app/
│   │   ├── api/                 # API 路由
│   │   ├── core/                # 核心配置
│   │   ├── models/              # 数据模型
│   │   ├── services/            # 业务逻辑
│   │   │   ├── ai_engine.py     # AI 生成引擎
│   │   │   ├── vector_search.py # 向量检索
│   │   │   ├── consistency.py   # 一致性检查
│   │   │   └── state_tracker.py # 状态追踪
│   │   └── main.py              # 应用入口
│   ├── prompts/                 # Prompt 模板
│   ├── requirements.txt
│   └── .env.example
│
├── storage/                     # 数据存储（Docker volume）
│   ├── projects/
│   └── vectorstore/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

## 关键配置

### 环境变量（.env）

```env
# AI API
SILICONFLOW_API_KEY=your_siliconflow_key
DEEPSEEK_API_KEY=your_deepseek_key

# Database
DATABASE_URL=postgresql://user:pass@db:5432/novel_workstation

# Embedding
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024

# Reranker (V2)
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

### 清新素雅样式规范

| 元素 | 规范 |
|---|---|
| 主背景 | `#FAFAFA` |
| 卡片背景 | `#FFFFFF` |
| 主文字 | `#333333` |
| 主色调 | `#5B9BD5`（淡青） |
| 强调色 | `#ED7D31`（暖橙） |
| 圆角 | 6-8px |
| 阴影 | `0 1px 3px rgba(0,0,0,0.05)` |
| 间距基数 | 8px |

## 验证标准

| 阶段 | 验收标准 |
|---|---|
| 阶段 1 | 前后端能启动，项目 CRUD 完成 |
| 阶段 2 | 能生成故事核心、世界观、角色 |
| 阶段 3 | 能生成章节，向量检索工作 |
| 阶段 4 | 能检测矛盾，伏笔追踪工作 |
| 阶段 5 | 功能完整，Docker 部署成功 |

## 注意事项

1. **API Key 安全**：不要硬编码，使用 `.env` 文件
2. **流式输出**：使用 SSE，避免超时
3. **向量切片**：500-800 字/片，不是整章
4. **一致性检查**：章节生成后自动触发
5. **风格一致性**：前端严格遵守清新素雅规范
