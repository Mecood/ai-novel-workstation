# AI 小说创作工作站 - 实施计划

## 总目标

构建一个完整的 AI 小说创作 Web 应用，支持从世界观设定→角色创建→章节生成的完整工作流。

**架构**：React + TypeScript 前端（清新素雅风格） + FastAPI 后端 + PostgreSQL + ChromaDB

---

## 阶段 1：项目框架搭建

### 1.1 后端初始化
- [x] 创建 `backend/` 目录
- [x] 创建 Python venv
- [x] 安装：fastapi, uvicorn, sqlalchemy, psycopg2-binary, pydantic, python-dotenv, alembic
- [ ] 创建 `backend/app/main.py` - FastAPI 入口
- [ ] 创建 `backend/app/core/config.py` - 配置管理
- [ ] 创建 `backend/app/core/database.py` - 数据库连接
- [ ] 创建 `backend/app/models/` - 数据模型（Project, StoryCore, Worldview, Character, Chapter）
- [ ] 创建 `backend/app/api/` - API 路由
- [ ] 创建 `backend/app/services/` - 业务逻辑层

### 1.2 前端初始化
- [ ] Vite + React 18 + TypeScript 初始化
- [ ] 安装：antd, @ant-design/icons, axios, react-router-dom, zustand
- [ ] 创建清新素雅全局样式
- [ ] 创建布局组件

### 1.3 Docker 配置
- [ ] 创建 `docker-compose.yml`（前端 + 后端 + PostgreSQL + ChromaDB）
- [ ] 创建 `.env.example`

### 1.4 项目 CRUD
- [ ] 后端：项目创建/列表/详情/删除
- [ ] 前端：项目列表页 + 详情页

---

## 阶段 2：AI 引擎集成

### 2.1 统一 AI 客户端
- [ ] `backend/app/core/ai_client.py` - 封装 LLM + Embedding 调用
  - 支持硅基流动 API、DeepSeek API
  - 统一的 prompt 构建 + 流式响应

### 2.2 Prompt 模板系统
- [ ] `backend/prompts/story_core.yaml` - 故事核心生成
- [ ] `backend/prompts/worldview.yaml` - 世界观设定
- [ ] `backend/prompts/character.yaml` - 角色设定
- [ ] `backend/prompts/chapter.yaml` - 章节生成

### 2.3 生成接口
- [ ] `POST /api/v1/projects/{id}/story-core/generate`
- [ ] `POST /api/v1/projects/{id}/worldview/generate`
- [ ] `POST /api/v1/projects/{id}/characters/generate`
- [ ] `POST /api/v1/projects/{id}/chapters/generate`（SSE 流式）

---

## 阶段 3：向量检索 + 状态管理

### 3.1 向量检索
- [ ] ChromaDB 集成：`backend/app/services/vector_search.py`
- [ ] Embedding 服务（BAAI/bge-m3 通过硅基流动 API）
- [ ] 文本切片策略（500-800 字/片）
- [ ] 上下文检索 + 前情提要

### 3.2 状态追踪
- [ ] `backend/app/services/state_tracker.py`
- [ ] 记录已生成内容
- [ ] 追踪角色出场情况
- [ ] 追踪伏笔状态

---

## 阶段 4：一致性检查

### 4.1 一致性检查
- [ ] `backend/app/services/consistency.py`
- [ ] S1（明显矛盾）：角色名错误、时间线冲突
- [ ] S2（一致性问题）：性格偏离、设定遗忘
- [ ] S3（审美/风格）：语气突变
- [ ] S4（漏洞）：逻辑缺口

### 4.2 伏笔管理
- [ ] 伏笔 CRUD 接口
- [ ] 状态追踪（planted / paid_off / abandoned）
- [ ] 未回收提醒

---

## 执行顺序

```
1. 后端框架（main.py, config, database, models）
2. 前端框架（Vite, Ant Design, 布局）
3. Docker Compose
4. 项目 CRUD + 页面联调
5. AI 客户端 + Prompt 模板
6. 生成接口 + SSE
7. 向量检索
8. 一致性检查
9. 测试 + 部署
```