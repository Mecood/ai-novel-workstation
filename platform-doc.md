# 《烛瞑》创作平台使用手册

> 最后更新：2026-07-29
> 作者：锦言
> 适用范围：后端 `ai-novel-workstation` 平台 v1（FastAPI + SQLite）

---

## 一、基本连接

### 后端 API

| 项目 | 值 |
|------|-----|
| Base URL | `http://127.0.0.1:9000/api/v1/` |
| 健康检查 | `GET /health` |
| 数据库 | `backend/novel_workstation.db`（SQLite） |

### 前端

| 项目 | 值 |
|------|-----|
| 开发地址 | `http://127.0.0.1:5173/projects/{project_id}/...` |
| 预览地址 | `http://127.0.0.1:4173` |
| 路径格式 | `/projects/{project_id}/{page}` |
| page 映射 | workshop / story-core / worldview / characters / outline / writing / foreshadowings / consistency / knowledges / prompts / reader / relationships / timeline / debts / contracts / export / writing-brief / settings |

> **注意**：前端路由用单数 `worldview`，不用复数 `worldviews`。`vite preview` 没有 API proxy，后端请求会失败，只有 `vite dev` 才有 proxy 到 9000 端口。

### ngrok 公网访问

```bash
~/bin/ngrok http 5173 --url=crib-pastel-deduct.ngrok-free.dev
```

公网 IP 请求（183.6.x.x / 209.9.x.x）会经过 ngrok 转发到本地 5173。

---

## 二、当前项目信息

| 项目 | 值 |
|------|-----|
| 书名 | 《烛瞑》 |
| Project ID | `0151dfc3-2686-4843-ab36-49105ef447cd` |
| 章节 ID (Ch1) | `5c0ba73c-eaa3-4b7c-9c3a-7616bab8d82a` |
| 卷 ID (Vol1) | `49c83c32-0285-4911-9b57-cd85b18c6494` |
| 世界观 ID | `54adb9af-b3ae-40e9-abd2-175f50bd7fba` |
| AI 供应商 | sensenova（active_provider=0） |
| AI 模型 | deepseek-v4-flash / sensenova-6.7-flash-lite |
| 字数要求 | 每章 4300-10000 字 |

### 后端配置

后端配置存在 `app_config` 表的 JSON 字段中：
```
config.active_provider = 0（整数索引，对应 providers[0] = sensenova）
config.providers[0].url = https://token.sensenova.cn/v1
config.providers[0].api_key = sk-GyqXgweuv6w2twZljIdILezuE7P7O2it
```

**重要**：`active_provider` 存的是 **整数索引（0/1）**，不是字符串名称。代码中做匹配时要用 `providers[idx]` 而非 `p["name"] == active`。

---

## 三、AI 生成端点（全部是 SSE 流式）

> **核心规则**：所有 `/generate` 和 `/regenerate` 端点都是 **Server-Sent Events (SSE)** 流式输出。
> - 用 `curl` 调用时必须用 `--no-buffer -N`（无缓冲、长连接）
> - Python `urllib` 调用时不能设 timeout 过短（SSE 流可能持续到 5-15 分钟）
> - SSE 格式：每行 `data: {"type":"chunk","text":"..."}` 或 `data: {"type":"done",...}`
> - **不要在 SSE 流上调用 `response.read()` 一次读完**——它会等到流结束

### 3.1 生成新章节（自动递增编号）

```
POST /projects/{project_id}/chapters/generate
```

行为：
1. 查询已有章节，计算 next_number
2. 检查该章节的 `_skeleton` 是否有效（CBN/CPNs/CEN 至少一个非空）——**无骨架会返回 400 拒绝生成**
3. 读世界观、角色、故事核心、已有章节、向量检索
4. 调用 AI 流式生成
5. 自动保存为新章节（status=generated），触发自动流水线（pipeline auto-advance）
6. 自动生成标题和摘要
7. 自动风格检测并写入 project.context

**前置条件**：章节必须有有效骨架（`_skeleton` 字段含 CBN 5 节拍或 CPNs 承诺清单或 CEN 事件清单）

### 3.2 重新生成已有章节

```
POST /projects/{project_id}/chapters/{chapter_id}/regenerate
```

行为：
1. 读取章节、世界观、角色、其他章节（不含本章节）
2. **不检查骨架**——可以直接调
3. 流式生成新内容
4. 自动保存版本历史（version_service）
5. 更新章节内容、字数、_stale=false

**关键约束**：
- `chapter_id` 是 UUID（不是 chapter_number）
- 该 API 通过 `EventSourceResponse` 返回，Python 调用需要用 `read()` 逐行读取

### 3.3 生成故事核心 / 世界观 / 角色

```
POST /projects/{project_id}/story-core/generate
POST /projects/{project_id}/worldview/generate
POST /projects/{project_id}/characters/generate
POST /projects/{project_id}/outline/generate
```

### 3.4 一致性检查

```
POST /projects/{project_id}/consistency/check
```

POST body 需要传入新内容和已有内容。

### 3.5 章节去 AI 味

```
POST /projects/{project_id}/chapters/{chapter_id}/de-ai
POST /projects/{project_id}/chapters/{chapter_id}/detect-ai
```

### 3.6 生成写作任务书

```
GET /projects/{project_id}/chapters/{chapter_number}/task-book
```

---

## 四、普通 CRUD 端点（非流式）

> 这些端点返回即时 JSON 响应，用 curl 直接调即可。

### 4.1 项目

```
GET  /projects/{project_id}                — 项目详情（含 story_core）
PUT  /projects/{project_id}                — 更新项目
POST /projects                             — 创建项目（InitWizard 调用）
```

### 4.2 章节

```
POST   /projects/{project_id}/chapters                 — 创建章节（传 ChapterCreate）
GET    /projects/{project_id}/chapters                 — 章节列表
PUT    /projects/{project_id}/chapters/{chapter_id}   — 更新章节（传 ChapterUpdate）
DELETE /projects/{project_id}/chapters/{chapter_id}   — 删除章节
GET    /projects/{project_id}/chapters/previous-summary — 前情提要
```

ChapterCreate 必要字段：`chapter_number` (int), `title` (str)
ChapterCreate 可选：`content` (JSON `{text: "..."}`), `summary`, `outline_detail`, `skeleton`, `content_marks`, `tags`, `group`

**注意**：`content` 存为 JSON 对象 `{"text": "..."}`，不是纯字符串。字数存到 `word_count` 字段。

### 4.3 卷

```
POST   /projects/{project_id}/volumes                    — 创建卷（传 VolumeCreate）
GET    /projects/{project_id}/volumes                    — 卷列表
PUT    /projects/{project_id}/volumes/{volume_id}        — 更新卷
DELETE /projects/{project_id}/volumes/{volume_id}        — 删除卷
```

VolumeCreate 字段：`title` (必填), `volume_number` (可选, 自动递增), `chapter_start` (默认1), `chapter_end`, `description`, `highlight_rhythm`, `emotion_arc`, `foreshadowing_notes`, `twists`

**注意**：卷通过 `chapter_start`/`chapter_end` 范围与章节关联（不是外键）。卷 ID 是 UUID。

### 4.4 角色

```
GET    /projects/{project_id}/characters                    — 角色列表
POST   /projects/{project_id}/characters                    — 创建角色
GET    /projects/{project_id}/characters/{character_id}     — 角色详情
PUT    /projects/{project_id}/characters/{character_id}     — 更新角色
DELETE /projects/{project_id}/characters/{character_id}     — 删除角色
GET    /projects/{project_id}/characters/stale-report       — 过期报告
GET    /projects/{project_id}/characters/arc                — 角色弧线
```

Character 关键 JSON 字段：`personality` (list[str]), `background` (text), `arc` (JSON), `relationships` (JSON)

### 4.5 世界观

```
GET    /projects/{project_id}/worldviews                        — 世界观列表
POST   /projects/{project_id}/worldviews                        — 创建世界观
PUT    /projects/{project_id}/worldviews/{worldview_id}        — 更新世界观
```

Worldview 字段：`name`, `description`, `rules` (JSON list), `timeline` (JSON list[{epoch, event}])

> **⚠️ BUG**：`PUT /worldviews/{id}` 更新时会调用 `stale_detection_service.check_and_mark_stale()`，该服务在遇到 `personality`（list 类型）时会报错 500。**临时方案**：直接用 sqlite3 更新 DB 绕过 API，或先确认 `_extract_text` 已修。已修复方案：在 `_extract_text` 中加入 `list/tuple` 分支。

### 4.6 故事核心

```
GET    /projects/{project_id}/story-core
PUT    /projects/{project_id}/story-core
```

PUT body 是 `StoryCoreData`（直接传 JSON 对象，自动存入 project.story_core JSON 字段）。

### 4.7 伏笔

```
POST   /projects/{project_id}/foreshadowings
GET    /projects/{project_id}/foreshadowings
PUT    /projects/{project_id}/foreshadowings/{foreshadowing_id}
POST   /projects/{project_id}/foreshadowings/{foreshadowing_id}/resolve
GET    /projects/{project_id}/foreshadowings/unresolved
GET    /projects/{project_id}/foreshadowings/dag
```

### 4.8 知识库

```
POST   /projects/{project_id}/knowledges
GET    /projects/{project_id}/knowledges
GET    /projects/{project_id}/knowledges/{knowledge_id}
PUT    /projects/{project_id}/knowledges/{knowledge_id}
```

### 4.9 事件

```
POST   /projects/{project_id}/events/{chapter_number}/extract  — 从章节提取事件
GET    /projects/{project_id}/events                           — 事件列表
GET    /projects/{project_id}/events/timeline                  — 事件时间线
GET    /projects/{project_id}/events/relationships             — 角色关系
```

### 4.10 伏笔债务

```
GET    /projects/{project_id}/debt/summary
GET    /projects/{project_id}/debt/chapter/{chapter_number}
POST   /projects/{project_id}/debt/accrue
GET    /projects/{project_id}/debt/reading-power
POST   /projects/{project_id}/debt/chapters/{chapter_number}/evaluate-reading-power
GET    /projects/{project_id}/debt/contracts
POST   /projects/{project_id}/debt/contracts
```

### 4.11 合同

**两个 router**：

Router A: `prefix="/projects/{project_id}/chapters/{chapter_number}"`
```
POST   /contract/sign        — 签署契约
GET    /contract              — 查看契约
POST   /commit               — 提交章节
GET    /commit                — 查看提交状态
GET    /commit/history        — 提交历史
GET    /contract/audit        — 审计日志
```

Router B: `prefix="/projects/{project_id}"` (project_router)
```
GET    /contracts/all         — 项目所有合同列表
```

> **注意**：合同 API 中 `chapter_number` 是数字编号（1, 2, 3...），不是 UUID。

### 4.12 评审

```
POST   /projects/{project_id}/chapters/{chapter_number}/review         — 触发评审（SSE 流式）
GET    /projects/{project_id}/chapters/{chapter_number}/review         — 获取评审报告
GET    /projects/{project_id}/reviews/trend                            — 评审趋势
GET    /projects/{project_id}/reviews/dimensions                       — 维度趋势
POST   /projects/{project_id}/reviews/{review_id}/decide               — 决定评审结果
POST   /projects/{project_id}/chapters/{chapter_number}/polish         — AI 润色
```

评审使用 `chapter_number`（数字），不是 UUID。评审报告 JSON 字段：`overall_score`, `dimension_scores`（设定一致性/时间线/叙事连贯/角色一致性/逻辑）, `severity_counts`, `issues`（含 `blocking` 字段）。

### 4.13 流水线

```
GET    /projects/{project_id}/pipeline
GET    /projects/{project_id}/pipeline/transitions
GET    /projects/{project_id}/pipeline/auto-advance
PATCH  /projects/{project_id}/pipeline/auto-advance
GET    /projects/{project_id}/pipeline/state
```

流水线阶段：init → plan → write → review → commit

### 4.14 自动流水线

```
POST   /projects/{project_id}/chapters/{chapter_id}/auto-pipeline
```

### 4.15 版本历史

```
GET    /projects/{project_id}/chapters/{chapter_id}/versions
GET    /projects/{project_id}/chapters/{chapter_id}/versions/{version}
POST   /projects/{project_id}/chapters/{chapter_id}/versions/{version}/restore
```

### 4.16 导出

```
POST   /projects/{project_id}/export/full                  — 导出整本 .docx
POST   /projects/{project_id}/export/chapter/{chapter_id} — 导出单章 .docx
GET    /projects/{project_id}/export/safe                  — 安全导出（exporter）
```

> **注意**：导出是 POST，不是 GET。返回的是文件流（.docx），curl 时用 `-o output.docx`。

### 4.17 搜索 / 导入

```
GET    /projects/{project_id}/search?query=...
POST   /importer/parse                                    — 解析导入文件
```

### 4.18 番茄钟 / 朱雀

```
GET    /tomato/export/{project_id}
POST   /tomato/zhuque-check
```

### 4.19 Prompt 模板

```
GET    /projects/{project_id}/prompt-templates
POST   /projects/{project_id}/prompt-templates
PUT    /projects/{project_id}/prompt-templates/{template_id}
DELETE /projects/{project_id}/prompt-templates/{template_id}
```

### 4.20 全局设置

```
GET    /settings
PUT    /settings
POST   /settings/test-connection
POST   /settings/fetch-models
```

---

## 五、Prompt 模板

| 类型 | 文件路径 |
|------|---------|
| 章节生成 | `backend/prompts/chapter.yaml` |
| 故事核心 | `backend/prompts/story_core.yaml` |
| 世界观 | `backend/prompts/worldview.yaml` |
| 角色 | `backend/prompts/character.yaml` |
| 大纲 | `backend/prompts/outline.yaml` |
| 一致性 | `backend/prompts/consistency.yaml` |
| 知识提取 | `backend/prompts/knowledge_extract.yaml` |
| 去 AI 味 | `backend/prompts/de_ai.yaml` |

**章节生成 prompt 关键约束**（`chapter.yaml`）：

```yaml
system:
  - 每章4300-10000字
  - 严格使用世界观提供的概念，不可自创
  - 章节结尾必须有钩子
user:
  - {name} 项目名称
  - {genre} 小说类型
  - {story_core} 故事核心
  - {worldview} 世界观
  - {characters} 角色
  - {prev_summary} 前情提要
  - {outline_section} 本章细纲
  - {style_section} 风格要求
  - {memory_*} 记忆系统
```

---

## 六、关键系统机制

### 6.1 骨架检查（Phase 7a）

生成章节前，`_has_valid_skeleton()` 检查章节的 `_skeleton` 字段：
- CBN（5节拍）：`skeleton.cbn.beats` 长度为 5
- CPNs（承诺清单）：`skeleton.cpns.promises` 非空
- CEN（事件清单）：`skeleton.cen.events` 非空

**任何一个满足即可**。没有骨架的章节无法通过 `POST /chapters/generate` 生成——会返回 400。

`regenerate` 端点**不检查骨架**，可以直接调。

### 6.2 记忆系统（memory_orchestrator）

生成时优先从记忆系统加载上下文：
- working_memory → prev_summary
- episodic_memory → 情节记忆
- semantic_memory → 长期记忆（世界观/角色/伏笔/知识）

记忆失败时回退：最近 3 章的摘要。

### 6.3 Stale（过期检测）

修改 worldview / character / story_core 后，`check_and_mark_stale()` 扫描已有章节和合同，将受影响的标记 `_stale="true"`。

> **已知问题**：`_extract_text()` 在处理 list 类型（如 `personality` 是 `list[str]`）时返回 `str(['...'])`，导致 JSON 解析失败。已修复——加入 `list/tuple` 分支。

### 6.4 版本系统

每次章节内容更新时 `version_service.save_and_bump()` 自动：
1. 保存旧内容到版本历史
2. 递增 `_version`
3. 记录 `_based_on`（依赖的 story_core/worldview/characters 版本）

可通过 `/versions/{version}/restore` 恢复到指定版本。

### 6.5 流水线自动推进

触发器：
- chapter_created → 自动推进到下一阶段
- volume_created → 检查并推进
- review_completed → 根据评审结果决定是否继续

### 6.6 风格检测（ai_flavor_detector）

章节生成后自动运行 `detect_ai_flavor()`，如果 AI 味 > 30，将 `style_guidance` 写入 `project.context`，供下一章生成时参考。

---

## 七、数据库操作

### 7.1 直接操作数据库（应急方案）

当 API 端点有 bug（如 stale 检测 500）时，可以用 sqlite3 直接操作：

```bash
cd /Users/products/code/ai-novel-workstation/backend
sqlite3 novel_workstation.db "SELECT ..."
```

**注意**：直接修改 DB 会绕过：
- 版本历史（`_history` / `_version`）
- Stale 检测
- 流水线推进
- 版本历史保存

**推荐做法**：先查 DB 确认状态 → 用 API 操作 → 如果 API 失败 → 直接操作 DB + 手动更新 _version

### 7.2 关键表结构

| 表 | 关键外键 | 重要 JSON 字段 |
|-----|---------|--------------|
| projects | id (PK) | story_core (JSON) |
| chapters | project_id → projects.id | content, outline_detail, _skeleton, tags, _history |
| characters | project_id → projects.id | personality (JSON list), arc (JSON) |
| worldviews | project_id → projects.id | rules (JSON list), timeline (JSON list) |
| volumes | project_id → projects.id | highlight_rhythm, emotion_arc, twists (全部 JSON) |
| foreshadowings | project_id, event_id | — |
| chapter_contracts | project_id, chapter_id | — |
| story_events | project_id | — |
| knowledges | project_id | — |
| chase_debts | project_id | — |
| pipeline_state | project_id | current_stage |
| review_reports | project_id, chapter_number | — |
| chapter_reading_power | project_id | — |
| app_config | id | config (JSON: providers, active_provider) |

### 7.3 章节 content 格式

```json
{"text": "正文内容……"}
```

`word_count` 存纯数字（`len(text)`）。

### 7.4 章节 _history 格式

```json
[
  {
    "timestamp": "2026-07-29T04:30:00",
    "action": "regenerate",
    "reason": "用户审查：xxx",
    "old_content_preview": "前200字"
  }
]
```

---

## 八、AI 模型直调（绕过平台时）

当平台 SSE 流式 API 无法调用时，可以直接调用 sensenova API：

```python
import urllib.request, json

payload = json.dumps({
    "model": "sensenova-6.7-flash-lite",
    "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
    "max_tokens": 12000,
    "temperature": 0.85,
    "stream": False
}, ensure_ascii=False)

url = "https://token.sensenova.cn/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk-GyqXgweuv6w2twZljIdILezuE7P7O2it"
}

req = urllib.request.Request(url, data=payload.encode('utf-8'), headers=headers, method='POST')
resp = urllib.request.urlopen(req, timeout=300)
data = json.loads(resp.read().decode('utf-8'))
content = data['choices'][0]['message']['content']
```

> **限制**：非流式调用 `max_tokens` 不能超过模型单次输出限制。sensenova-6.7-flash-lite 单次最多约 8000 tokens。
> 如果内容超过限制，需要分批生成或启用 `stream: True`。

---

## 九、uvicorn 重启

后端服务重启步骤（不要带 `--reload`，避免端口冲突）：

```bash
cd /Users/products/code/ai-novel-workstation/backend

# 1. 杀掉旧进程
kill -9 $(lsof -ti:9000) 2>/dev/null

# 2. 清除 Python 字节码缓存
find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null

# 3. 启动（后台）
.venv/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 9000 &

# 4. 验证
sleep 2
curl -s http://127.0.0.1:9000/health
```

> macOS 上 uvicorn 进程容易被 Jetsam SIGTERM（内存压力），如果重启失败先清 cache 再试。

---

## 十、常见错误与处理

| 错误 | 原因 | 处理 |
|------|------|------|
| "AI 未配置" (400) | active_provider 索引匹配失败 | 检查 config.active_provider（是 int 索引不是字符串） |
| "badly formed hexadecimal UUID string" | 某行数据 UUID 格式错误 | 查具体表的 ID 字段是否有非 36 位字符 |
| 世界观更新 500 | stale 检测 _extract_text 处理 list 类型失败 | 已修复，确认 stale_detection_service.py 有 list 分支 |
| "第 N 章未定义骨架" (400) | _skeleton 为空 | 先创建章节条目 + skeleton，再用 generate |
| 章节字数 0 但内容有字 | DB 中 word_count 字段未更新 | 更新 word_count = len(content.text) |
| 前端显示与 DB 不一致 | Vite HMR 缓存 | 浏览器硬刷新 |
| ngrok 请求但本地看不到 | ngrok 转发到 vite dev（5173），vite dev 有 proxy 到 9000 | 确认 vite dev 在运行 |
| "No routes matched" | 路由名写错（复数 vs 单数） | 确认是 worldview（单数），不是 worldviews |

---

## 十一、《烛瞑》专属状态

### 已完成（设定对齐）

- 卷描述已对齐："地脉勘测师林渊发现灵矿司五行地脉工程秘密"
- 世界观已重写：5 条规则 + 5 个时间点，与第一章正文同源
- 故事核心已补齐：one_sentence 含林渊/灵矿司/精卫/帝江
- 角色表：林渊(主)、沈青瑶(配)、陈中岳(反派)、小灵(配)
- 第一章已生成 6064 字（旧版，待重新生成）
- 第一章评审：overall 95.17（但评审记录是基于旧版的）
- prompt 模板已修正字数 4300-10000 + 概念约束
- stale 检测 bug 已修复（_extract_text list 分支）

### 待完成

- 第一章重新生成（含主角名字林渊自然出现）
- 第一卷 2-12 章细纲补全
- 各章细纲写入 outline_detail 字段
- 逐章生成（第 2-12 章）
