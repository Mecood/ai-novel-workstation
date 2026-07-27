# AI Novel Workstation 融合升级 — 实施规格说明书

> 版本：v1.0 · 角色：锦言（织文者）出规格
> 参考项目：CharacterArc（github.com/uu201/character-arc）
> 总工作量：6.5 人天（后端 2.5 + 前端 3.5 + 联调 0.5）

---

## Phase 1: Skill 体系

### 1.0 架构总览

```
启动时
  backend/app/skills/ 目录
    ↓ 扫描所有 SKILL.md
  SkillRegistry（内存单例）
    ↓ 按 task 匹配
  AIService.chat_with_skills(task, user_prompt)
    → skill_prompts 作为系统消息前缀注入
    → 原有 chat() 逻辑不变
```

### 1.1 新建/修改文件

| 操作 | 路径 |
|------|------|
| 新建 | `backend/app/services/skill_registry.py` |
| 新建 | `backend/app/models/skill.py` |
| 新建 | `backend/app/api/v1/skills.py` |
| 新建 | `backend/app/schemas/skill.py` |
| 新建 | `frontend/src/pages/project/SkillsPage.tsx` |
| 修改 | `backend/app/services/ai_service.py`（加 `_inject_skills()` 方法） |
| 修改 | `backend/app/api/v1/__init__.py`（注册 skills 路由） |
| 修改 | `frontend/src/services/api.ts`（加 skillsApi） |
| 修改 | `frontend/src/App.tsx`（加 /skills 路由） |
| 提供 | `backend/app/skills/writing/story-chapter-exec/SKILL.md`（示例） |
| 提供 | `backend/app/skills/style/humanizer-zh/SKILL.md`（示例） |

### 1.2 Skill 文件格式

```markdown
---
name: story-chapter-exec
category: writing
description: 章节执行 - 按大纲节点生成章节正文
version: 1.0.0
tasks: [generate_chapter, chapter_write]
triggers: [用户请求生成章节, AI 续写]
priority: 5
---

# 章节执行

## 核心原则
1. 章节长度控制在 2000-5000 字...
```

### 1.3 数据模型

```python
# backend/app/models/skill.py
class ProjectSkill(Base):
    __tablename__ = "project_skills"
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"))
    skill_name = Column(String(255), nullable=False)       # e.g. "story-chapter-exec"
    skill_category = Column(String(100), nullable=False)   # e.g. "writing"
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
```

> 注意：不新建 `skills` 表。Skill 定义存在文件系统中（`SKILL.md`），只在 DB 记录每个 project 启用了哪些 skill。

### 1.4 SkillRegistry 设计

```python
# backend/app/services/skill_registry.py

@dataclass
class SkillDefinition:
    name: str
    category: str
    description: str
    version: str
    tasks: list[str]
    triggers: list[str]
    priority: int
    content: str          # SKILL.md body（去 YAML frontmatter）
    file_path: str

class SkillRegistry:
    """单例：启动时扫描 skills/ 目录"""
    _instance: 'SkillRegistry | None' = None
    _skills: dict[str, SkillDefinition] = {}   # name → SkillDefinition
    _by_task: dict[str, list[str]] = {}         # task → [skill_names]

    @classmethod
    def get_instance(cls) -> 'SkillRegistry': ...
    def scan_directory(self, base_path: str) -> None: ...
    def get_skills_for_task(self, task: str) -> list[SkillDefinition]: ...
    def list_all(self) -> list[SkillDefinition]: ...
```

### 1.5 API 设计

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/skills` | 列出所有内置 skill（从 registry） |
| `GET` | `/api/v1/projects/{id}/skills` | 查询项目启用的 skill |
| `POST` | `/api/v1/projects/{id}/skills` | 为项目启用 skill `body: {skill_name: str}` |
| `DELETE` | `/api/v1/projects/{id}/skills/{skill_name}` | 停用 |

### 1.6 AI 注入方式（不改现有代码）

在 `ai_service.py` 加一个方法：

```python
async def chat_with_skills(self, db, task: str, user_prompt: str, 
                            base_system_prompt: str = "", project_id: str = None,
                            **kwargs) -> str:
    """原有 chat() 的包装：自动注入匹配的 Skill prompt。"""
    registry = SkillRegistry.get()
    skills = registry.get_skills_for_task(task)
    
    # 如果 project_id 给了，只取项目启用的
    if project_id:
        enabled = await self._get_project_skills(db, project_id)
        skills = [s for s in skills if s.name in enabled]
    
    # required skills 直接注入
    skill_context = "\n\n".join(
        f"## Skill: {s.name}\n{s.content[:2000]}" for s in skills
    )
    full_system = f"{system_prompt}\n\n{skill_context}" if skill_context else system_prompt
    messages = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": user_prompt},
    ]
    return await self.client.chat(messages, **kwargs)
```

现有方法（`generate_story_core` 等）暂时不碰，新功能逐步迁移到 `chat_with_skills`。

### 1.7 前端 SkillsPage

- **路由**：`/project/:id/skills`
- **布局**：Card → Table（columns: Skill 名称、分类、描述、状态 Toggle Switch）
- 三列表：**内置 Skill**（来自 GET /skills，只读）+ **项目 Skill**（来自 GET /projects/{id}/skills，可启用/停用）
- 操作：Switch on → POST 启用；Switch off → DELETE 停用

---

## Phase 2: 关系图谱

### 2.0 架构总览

```
RelationshipPage.tsx
  ↓ 使用 charactersApi.list(id) 拿到所有角色
  ↓ 解析每个角色的 relationships JSON
  ↓ 构建 G6 Graph Data（nodes + edges）
  ↓ 用 AntV G6 的 Graph 实例渲染力导向图
  ↓ 点击节点 → 跳转角色详情 / 弹窗显示
```

### 2.1 新建/修改文件

| 操作 | 路径 |
|------|------|
| 修改 | `frontend/src/pages/project/RelationshipPage.tsx` |
| 新增 | `frontend/src/components/charts/G6CharacterGraph.tsx`（独立组件） |
| 安装 | `@antv/g6`（npm 包） |

### 2.2 数据流

```
characters = GET /api/v1/projects/{id}/characters
→ CharacterResponse[] 包含 relationships: [{character_id, type, description?}]
→ 节点：{id: c.id, label: c.name + "\n" + c.role_type, color: ROLE_COLORS}
→ 边：{source: c.id, target: rel.character_id, label: rel.type, color: REL_COLORS[rel.type]}
```

### 2.3 G6 配置

```typescript
const graphOptions = {
  layout: { type: 'force', preventOverlap: true, nodeStrength: -50, edgeStrength: 0.1 },
  defaultNode: { type: 'circle', size: 50, labelCfg: { style: { fontSize: 12 } } },
  defaultEdge: { style: (model) => ({ stroke: model.color || '#8c8c8c' }) },
  modes: { default: ['drag-canvas', 'zoom-canvas', 'drag-node'] },
};
```

### 2.4 Role colors

- 主角 #1890ff、反派 #ff4d4f、主要配角 #faad14、普通 #8c8c8c
- 边配色沿用现有 `REL_COLORS`（师徒/情侣/兄弟/敌对/主仆/战友/其他）

### 2.5 保持不变

- 不需要改后端 API（`/characters` 已返回 `relationships` 字段）
- 不需要改变数据模型
- 电子邮件不新建（只增强用 React 图表实现 view Graph 的新方式，同时保留 ECharts 选择器）

---

## Phase 3: 富文本编辑器（Tiptap）

### 3.0 架构总览

```
WritingPage.tsx
    原始：<Input.TextArea value={editingContent} onChange={...} />
    替换为：<TiptapEditor content={editingContentHTML} onUpdate={(html) => handleEditorUpdate(html)} />
```

重要约束：后端 Chapter 的 `content` 字段仍然是 JSON `{text: "..."}`，存储纯文本，不存储 HTML。编辑器仅在渲染层做 HTML 格式化，保存时把 HTML 展平为纯文本。

### 3.1 安装

```bash
pnpm add @tiptap/react @tiptap/starter-kit @tiptap/extension-underline
```

### 3.2 编辑组件

新建 `frontend/src/components/editor/TiptapEditor.tsx`：
```tsx
interface TiptapEditorProps {
  value: string;              // 纯文本
  onChange: (text: string) => void;
  editable?: boolean;
  height?: number;           // 默认 400
}
```

内部：
1. mount 时用 `editor.commands.setContent(value)` 初始化（Tiptap starter-kit 会解析 `**粗体**`、`*斜体*` 等 Markdown 标记）
2. 每次内容变化时，用 `editor.getText()` 取纯文本 → `onChange(text)` 回调
3. 工具栏：Bold、Italic、Underline、Strike、Heading 1-3、Blockquote、Bullet List、Ordered List、Undo、Redo

### 3.3 工具栏组件

```tsx
const Toolbar = ({ editor }: { editor: Editor }) => (
  <Space wrap style={{ marginBottom: 8 }}>
    <Button onClick={() => editor.chain().focus().toggleBold().run()} type={editor.isActive('bold') ? 'primary' : 'default'}>B</Button>
    <Button onClick={() => editor.chain().focus().toggleItalic().run()} ...>I</Button>
    ...
  </Space>
);
```

### 3.4 集成到 WritingPage

修改 `WritingPage.tsx`：
- 删除 `const { TextArea } = Input;` 导入
- 替换 `<Input.TextArea ...>` 为 `<TiptapEditor value={editingContent} onChange={(text) => setEditingContent(text)} height={500} />`
- `handleSave` 保持不变——`editingContent` 还是纯文本

### 3.5 数据兼容

- `content.text` 保持不变（后端不做任何改动）
- 编辑器显示：Tiptap 会把纯文本按段落分行渲染，Markdown 标记如 `**粗体**` 会被渲染为 Bold（Tiptap 会自动转换）
- 保存时：`editor.getText()` 返回纯文本，**不保留 HTML**

---

## Phase 4: 章节版本历史

### 4.0 架构

```
Chapter 更新时
  ↓ 触发 ChapterService.update
  ↓ 从旧快照复制到 chapter_versions 表
  ↓ 前端「版本历史」面板
  ↓ API：GET /projects/{id}/chapters/{n}/versions
  ↓ API：POST /projects/{id}/chapters/{n}/versions/{vid}/restore
```

### 4.1 新建/修改文件

| 操作 | 路径 |
|------|------|
| 新建 | `backend/app/models/chapter_version.py` |
| 新建 | `backend/app/api/v1/chapter_versions.py`（版本 API） |
| 修改 | `backend/app/api/v1/chapters.py`（写入时触发快照） |
| 修改 | `frontend/src/pages/project/WritingPage.tsx`（版本面板） |
| 修改 | `frontend/src/services/api.ts`（加 versionApi） |

### 4.2 数据模型

```python
class ChapterVersion(Base):
    __tablename__ = "chapter_versions"
    id = Column(GUID, primary_key=True)
    chapter_id = Column(GUID, ForeignKey("chapters.id"))
    version_number = Column(Integer, nullable=False)       # 1, 2, 3...
    title = Column(String(255))
    content_json = Column(JSON)                            # 完整 content
    word_count = Column(Integer)
    created_at = Column(DateTime, default=func.now())
```

### 4.3 快照触发

在 `chapters.py` 的 update 端点：
```python
# 保存旧版本
if chapter.content != data.content:
    db.get(select(ChapterVersion).where(chapter.id...latest))
    version = ChapterVersion(chapter_id=chapter.id, version_number=chapter._version, content=chapter.content, ...)
    db.add(version)
    chapter._version += 1
```

### 4.4 API

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/projects/{id}/chapters/{n}/versions` | 列出该章节所有历史版本 |
| `POST` | `/projects/{id}/chapters/{n}/versions/{vid}/restore` | 还原该版本（把版本快照写回 chapter） |

### 4.5 前端版本面板

在 WritingPage.tsx 加一个折叠面板（Collapse）：
- 标题：📋 版本历史（当前版本号 v{chapter._version}）
- 内容：时间线列表，每个版本一行 {created_at: time, word_count: 字数, version_number: 版本号}
- 按钮项：查看该版本（Modal 弹窗），还原该版本（按钮）

---

## Phase 5: Agent Loop

### 5.0 架构总览

当前模式：`AIClient.chat(messages)` → 单次调用

目标模式：`AIClient.chat_tool_loop(system_prompt, tools, max_steps=8)` → 多步循环

### 5.1 实现方式

```python
class AIClient:
    async def chat_tool_loop(
        self, system_prompt: str, user_prompt: str,
        tools: list[dict], task_name: str = "",
        max_steps: int = 8,
    ) -> dict:
        result = {"final_text": "", "iterationsN": 0, "tool_calls": [], "usage": {}}
        conversation = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        for step in range(max_steps):
            # 1. 调用 LLM
            response = await self.chat(conversation, tools=tools, ...)
            
            # 2. 如果有 tool_calls，执行工具
            if response.tool_calls:
                tool_results = execute_tools(response.tool_calls)
                record_call(response.tool_calls)
                conversation.append(tool_results)
                continue
            
            # 3. 如果没有 tool_calls，任务结束
            result.final_text = response.text
            break
        
        return result
```

### 5.2 Tool 设计

```python
# backend/app/services/agent_tools.py

class ChapterTool:
    @staticmethod
    async def read_chapter(db, chapter_id) → chapter_content
    @staticmethod
    async def read_outline(db, project_id) → outline_text
    @staticmethod
    async def read_character(db, character_id) → character_data
    @staticmethod
    async def read_worldview(db, project_id) → world_rules
    @staticmethod
    async def search_knowledge(db, project_id, query) → relevant_docs
```

### 5.3 集成方式

- **不改现有 `ai_service.py` 的方法** — 现有代码不动
- 首次接入只应用于 `polish_service.py` 的 4 步修复流程中的第一步 `_fix_issues`（需要多次读上下文）
- 后续逐步迁移其他需要复杂上下文的任务

---

## Phase 6: 导出 .docx

### 6.1 新建/修改

| 操作 | 路径 |
|------|------|
| 新建 | `backend/app/services/docx_exporter.py` |
| 新建 | `backend/app/api/v1/export.py` |
| 修改 | 前端阅读/写作页面加导出按钮 |
| 安装 | `python-docx`（pip） |

### 6.2 docx 生成逻辑

```python
async def export_chapter_to_docx(chapter: Chapter) -> bytes:
    from docx import Document
    doc = Document()
    doc.add_heading(chapter.title, level=1)
    doc.add_paragraph(text)     # audi chapter.paragraphs 或 content.text
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
```

### 6.3 API

`GET /api/v1/projects/{id}/chapters/{n}/export?format=docx` → 返回 .docx 流

---

## 风险点与应对

| 风险 | 概率 | 应对 |
|------|:---:|------|
| Tiptap 在 Mac 上性能不佳（大段文字编辑时） | 中 | 使用 `@tiptap/extension-placeholder` 和 `@tiptap/extension-character-count` 做性能监控 |
| 前期 Tiptap 引入了 HTML 存储需求 | 低 | 明确规范：编辑器仅纯文本写入，不做 HTML 转换 |
| Agent Loop 的 tool 设计步数增加时爆 | 中 | 先限制 max_steps=4，等稳定再提高 |
| 关系图谱 100+ 节点时性能差 | 低 | 节点数 < 80（角色的用户不会太多）；如果超过 => 把同类型角色分组 cluster |

---

*锦言（织文者）· 2026-07-27*