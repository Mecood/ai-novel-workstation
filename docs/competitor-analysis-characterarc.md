# 竞品分析报告：CharacterArc（弧光）vs AI Novel Workstation

> 调研日期：2026-07-27
> 调研对象：https://github.com/uu201/character-arc（389 ★, 62 forks, MIT, 2026-05-24 创建）

---

## 一、CharacterArc 项目概览

CharacterArc（弧光）是一款 **AI 小说创作桌面应用**，定位为"围绕小说项目组织、章节写作与 AI 协作的桌面工作台"。

### 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | **Electron** + Vue 3 + TypeScript |
| 状态管理 | Pinia |
| UI 组件 | Naive UI |
| 构建工具 | electron-vite (Vite 7) |
| 富文本编辑器 | **TipTap** |
| 关系图谱 | **Cytoscape** |
| 持久化 | **SQLite**（主进程） |
| AI SDK | **Vercel AI SDK** (@ai-sdk/openai, @ai-sdk/anthropic) |
| 文档解析 | mammoth (.docx)、marked (Markdown) |

### 核心定位
- 🏠 **本地优先** — 数据存本机 SQLite，完全离线可控
- 📦 **项目隔离** — 每项目独立维护设定、章节、知识库、AI 运行记录
- 📖 **章节导向** — 所有功能最终围绕章节创作落地
- 🧩 **Skill 驱动** — AI 调用按任务自动匹配内置/项目级 Skill，支持 Agent Loop
- 🌐 **多厂商接入** — 所有 OpenAI 兼容接口 + Anthropic 协议

---

## 二、架构对比

### CharacterArc 架构

```
┌─────────────────────────────────────────────────┐
│              Electron 主进程                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ 窗口管理  │  │  SQLite  │  │    AI 管线      │ │
│  │          │  │ 读写/迁移 │  │ 调度→Skill→模型  │ │
│  └──────────┘  └──────────┘  └────────────────┘ │
├───────────────── IPC 桥接 ──────────────────────┤
│              Vue 渲染层                           │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │  Pinia   │  │  TipTap  │  │  Naive UI 组件 │ │
│  │  Store   │  │  编辑器  │  │                │ │
│  └──────────┘  └──────────┘  └────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 我们的架构

```
┌─────────────────────────────────────────────────┐
│              FastAPI 后端                        │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ PostgreSQL│  │ ChromaDB │  │  Auto Pipeline  │ │
│  │  数据库   │  │ 向量检索 │  │ (review+polish) │ │
│  └──────────┘  └──────────┘  └────────────────┘ │
├───────────────── REST API ───────────────────────┤
│             React/Vite 前端                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ TypeScript│  │ Ant Design│ │ 多 Agent 委派  │ │
│  │          │  │  13 页面  │  │ (delegate_task)│ │
│  └──────────┘  └──────────┘  └────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 核心差异

| 维度 | CharacterArc | 我们的项目 |
|------|-------------|-----------|
| **运行形态** | 桌面应用（Electron） | Web 应用（前后端分离） |
| **部署方式** | 打包成 .dmg/.exe，单机安装 | 服务端部署，浏览器访问 |
| **数据库** | SQLite（单机） | PostgreSQL（多用户可共享） |
| **向量检索** | 无（用知识库文档+关键词） | ChromaDB（语义向量） |
| **AI 引擎** | Vercel AI SDK + 本地 Agent Loop | 自定义 prompt 工程 + 多模型 |
| **协作能力** | 单人单机 | 可多人访问同一项目 |
| **跨平台** | Windows/macOS | 任意有浏览器的设备 |

---

## 三、功能矩阵对比

### 3.1 项目管理

| 功能 | CharacterArc | 我们的项目 | 评价 |
|------|:-----------:|:--------:|------|
| 项目创建/编辑/删除 | ✅ | ✅ | 持平 |
| 新建向导（题材/篇幅/简介） | ✅ AI 生成首批设定 | ✅ | 持平 |
| 多项目隔离 | ✅ 原生支持 | ✅ 原生支持 | 持平 |
| 项目导入/导出 | ✅ JSON 快照 | ❌ | 落后 |
| 平台定向（番茄/起点/晋江） | ✅ 封面工作台支持 | ❌ | 落后 |

### 3.2 世界观与设定管理

| 功能 | CharacterArc | 我们的项目 | 评价 |
|------|:-----------:|:--------:|------|
| 世界观设定 CRUD | ✅ | ✅ | 持平 |
| 角色管理 | ✅ 含 avatar、tags | ✅ | 持平 |
| 组织/势力管理 | ✅ 含格言、配色 | ✅ | 持平 |
| **关系图谱可视化** | ✅ Cytoscape 力导向图 | ❌ | **落后** |
| 组织成员关系 | ✅ 成员表+关系图 | ❌ | 落后 |
| 角色标签/人设 | ✅ JSON tags | ❌ 基础版 | 落后 |

### 3.3 大纲与剧情

| 功能 | CharacterArc | 我们的项目 | 评价 |
|------|:-----------:|:--------:|------|
| 分卷管理 | ✅ | ✅ | 持平 |
| 大纲节点 | ✅ 含标题/冲突/摘要/字数 | ✅ | 持平 |
| 拖拽排序 | ✅ 双栏交错时间线 | ❌ | **落后** |
| AI 扩写大纲 | ✅ 内置 | ✅ auto_pipeline 含 | 持平 |
| 按大纲新建章节 | ✅ 自动带入标题/摘要/字数 | ✅ 有绑定 | 持平 |
| 伏笔/线索追踪 | ✅ plot_threads 表 | ❌ | **落后** |
| 灵感面板 | ✅ 按分卷维护 | ❌ | 落后 |

### 3.4 章节创作

| 功能 | CharacterArc | 我们的项目 | 评价 |
|------|:-----------:|:--------:|------|
| 富文本编辑 | ✅ TipTap（格式化/搜索替换） | ❌ 纯文本 textarea | **落后** |
| 自动保存+版本历史 | ✅ 防抖写回+手动快照+回滚 | ❌ | **落后** |
| 字数目标跟踪 | ✅ 按章节设置+完成度 | ✅ | 持平 |
| 阅读/专注模式 | ✅ | ❌ | 落后 |
| 导出 .txt/.docx | ✅ | ❌ | 落后 |
| 三栏布局（目录+编辑+AI） | ✅ | ❌ 分页面 | 落后 |
| 章节内联 AI 侧边栏 | ✅ | ❌ 独立页面 | 落后 |

### 3.5 AI 能力

| 功能 | CharacterArc | 我们的项目 | 评价 |
|------|:-----------:|:--------:|------|
| **Skill 系统（28 个内置）** | ✅ oh-story-claudecode + community + Distilled-Novel-Toolbox | ❌ | **大幅落后** |
| **Agent Loop 工具循环** | ✅ runAgent 8-16 步多工具调用 | ❌ 单次调用 | **大幅落后** |
| **全局助手 v2** | ✅ 跨项目检索+暂存变更审阅+上下文路由 | ❌ | **落后** |
| 一致性评审（Tiered L1-L3） | ❌ 基础章节分析 | ✅ 我们独有 | **我们领先** |
| 一致性修复（Polish 4 步） | ❌ 基础润色 | ✅ 定点修复+风格适配+排版+AI味检测 | **我们领先** |
| 章节润色/续写/改写 | ✅ 多 handler | ✅ | 持平 |
| AI 初稿流式生成 | ✅ | ✅ | 持平 |
| 输出校验+自动修复 | ✅ 2 次 repair attempt | ❌ | 落后 |
| JSON 结构化输出 | ✅ handler.normalize+validate | ❌ 文本解析 | 落后 |
| 模型调用日志（usage/iteration） | ✅ ai_runs 表全量记录 | ❌ | 落后 |
| 多模型配置（多 profile） | ✅ AI Profiles 切换 | ❌ 单配置 | 落后 |

### 3.6 知识库与参考

| 功能 | CharacterArc | 我们的项目 | 评价 |
|------|:-----------:|:--------:|------|
| 知识库文档 | ✅ knowledge_documents | ✅ | 持平 |
| 参考作品导入 | ✅ .docx/.md 解析 | ✅ | 持平 |
| **参考作品深度拆解** | ✅ 风格分析/知识条目/仿写 | ✅ 有拆解功能 | 持平 |
| **风格指纹提取** | ✅ style-fingerprint Skill | ❌ | 落后 |
| **风格融合** | ✅ style-fusion Skill | ❌ | 落后 |
| 本地知识检索 | ✅ knowledge-retrieval.ts | ✅ ChromaDB 向量 | 不同方案 |
| 创作记忆面板 | ✅ workflow_documents 按分卷 | ❌ | 落后 |

### 3.7 特色功能

| 功能 | CharacterArc | 我们的项目 |
|------|:-----------:|:--------:|
| **封面工作台** | ✅ 多平台 Prompt 生成+历史版本对比+图像模型调用 | ❌ |
| **去 AI 味 Skill** | ✅ humanizer-zh + novel-anti-detection + novel-polishing | ✅ 内置（PolishService anti_ai_final） |
| 网文商业化 Skill | ✅ novel-commercialization | ❌ |
| 平台合规 Skill | ✅ novel-compliance（敏感词/规则） | ❌ |
| 爽点设计 Skill | ✅ novel-pleasure-points | ❌ |
| 情绪曲线 Skill | ✅ novel-emotion | ❌ |

---

## 四、深度分析：CharacterArc 的核心竞争力

### 4.1 Skill 驱动架构（最大差异化优势）

CharacterArc 拥有 **28 个内置 Skill**，分三个来源：

- **oh-story-claudecode**（12 个）：核心网文写作工作流，涵盖长篇/短篇/章节执行/拆文/扫榜/封面/去 AI 味/故事蓝图/番茄排版
- **community-skills**（3 个）：通用风格与润色（humanizer-zh、style-fingerprint、style-fusion）
- **Distilled-Novel-Toolbox**（13 个）：工程化网文知识库（题材/人设/世界观/节奏/情绪/爽点/润色/平台/合规/反检测）

每个 Skill 是一个 `SKILL.md` 文件，由 `registry` 扫描注册，`matcher` 按任务匹配。AI 调用时：
- required skills 直接注入系统提示
- optional skills 在 skill index 中列出，Agent 自行决定是否调用
- 支持项目级 Skill 包导入

**对比我们**：我们只有单 prompt 工程，没有 Skill 体系。这是最大的差距。

### 4.2 Agent Loop（多工具循环调用）

CharacterArc 使用 `runAgent` 函数实现多步工具循环：

```typescript
const loopResult = await runAgent({
  systemPrompt,
  userPrompt,
  tools,              // skillTools + knowledgeTools + chapterTools + projectDataTools
  maxTokens: 16000,
  maxSteps: resolveAgentMaxSteps(task.task)  // 8-16 步
})
```

Agent 可以：
- 多轮调用工具（读项目数据 → 读知识文档 → 写章节 → 校验）
- 按任务动态调整最大步数（deep-analyze 16 步，outline-batch 10 步，默认 8 步）
- 输出 JSON 失败自动修复（2 次 repair attempt）
- 全量记录 tool_calls、usage、iteration 数

**对比我们**：我们是一次性 prompt → 输出，没有工具调用循环。

### 4.3 关系图谱（Cytoscape）

使用 Cytoscape.js 力导向布局可视化角色关系和组织关联。数据模型完整：
- character_relationships（from/to 角色、关系类型、描述、强度 1-10）
- organization_memberships（角色+组织+角色+备注）

**对比我们**：完全没有。

### 4.4 全局助手 v2

Assistant Runtime v2 支持：
- 跨项目资料检索
- 设定修改与审计沉淀
- 暂存变更审阅（staged changes）
- 上下文路由（自动匹配需要的知识）

### 4.5 本地优先 + 数据可控

所有数据存本机 SQLite，不上传任何第三方服务。对于内容创作者来说，这是重要的隐私优势。

**对比我们**：我们用 PostgreSQL，数据在服务端。对于商用场景更安全（多用户/备份），但对于单机创作场景隐私不如 SQLite。

---

## 五、对比总结

### 我们领先的地方

| 维度 | 说明 |
|------|------|
| **一致性评审（Tiered L1-L3）** | CharacterArc 完全没有结构化的一致性检测，只有基础章节分析。我们的 L1 硬指标 + L2 软指标 + L3 终审是独特能力 |
| **一致性修复（4 步 Polish）** | CharacterArc 没有自动修复能力。我们的定点修复→风格适配→排版→AI 味终检是完整闭环 |
| **多 Agent 委派** | 我们支持子 agent 并发处理（delegate_task），CharacterArc 是单 Agent Loop |
| **向量语义检索（ChromaDB）** | CharacterArc 用关键词检索，我们用向量语义，召回更准 |
| **Web 部署** | 可多用户/多设备访问，不绑定单机 |

### 我们落后的地方

| 维度 | 差距程度 | 说明 |
|------|:------:|------|
| **Skill 系统** | 🔴 严重 | 28 个内置 Skill 是完整的方法论库，我们没有 |
| **Agent Loop 工具循环** | 🔴 严重 | 多步工具调用 vs 单次 prompt，能力差距很大 |
| **关系图谱可视化** | 🟡 中等 | Cytoscape 力导向图，我们没有 |
| **富文本编辑器** | 🟡 中等 | TipTap vs textarea，用户体验差距明显 |
| **伏笔/线索追踪** | 🟡 中等 | plot_threads 完整的数据模型 |
| **版本历史+快照** | 🟡 中等 | 章节版本回滚 |
| **封面工作台** | 🟢 轻微 | 多平台封面生成 |
| **参考作品深度拆解** | 🟢 轻微 | style-fingerprint/style-fusion |
| **AI 运行日志** | 🟢 轻微 | ai_runs 表全量记录 |

### 我们的独特优势

| 优势 | 说明 |
|------|------|
| **AI 一致性引擎** | 业界少有的小说结构一致性检测+自动修复能力 |
| **多 Agent 并发** | 可同时处理多个章节的审查/修复 |
| **向量知识库** | ChromaDB 语义检索比关键词更精准 |
| **Web 原生** | 无需安装，浏览器即用 |
| **API 友好** | REST 接口，可集成第三方工具 |

---

## 六、建议行动项

### 高优先级（应尽快补齐）

1. **Skill 体系** — 建立类似 CharacterArc 的 Skill 注册机制，把现有 prompt 工程拆成可复用的 Skill 包。可以借鉴 Distilled-Novel-Toolbox 的 13 个 Skill
2. **Agent Loop** — 支持多步工具调用，让 AI 能自己查知识、读章节、校验输出后再回答
3. **关系图谱** — 用 AntV G6 或类似库实现角色关系可视化

### 中优先级

4. **富文本编辑器** — 替换 textarea 为 ProseMirror 或 Tiptap（与 CharacterArc 同栈）
5. **章节版本历史** — 每次修改自动快照，支持回滚
6. **伏笔/线索追踪** — 增加 plot_threads 功能

### 低优先级

7. 封面工作台
8. 参考作品风格分析
9. 导出 .docx/.txt

---

## 七、结论

CharacterArc 是一款**定位精准、完成度很高**的小说创作桌面应用。它的核心竞争力在于：

- **Skill 体系**（28 个内置技能 + 可扩展）
- **Agent Loop**（多步工具调用）
- **完整的创作工作流**（项目→设定→大纲→章节→封面，一站式）

我们在**一致性检测与修复**这个方向上有独特优势，是 CharacterArc 完全没有的能力。

但如果要正面竞争，我们需要补齐 Skill 体系和 Agent Loop 这两个核心能力。建议在保持现有一致性引擎优势的前提下，逐步引入 Skill 框架和多步 Agent 调用。

---

*报告生成：锦言（织文者）· 2026-07-27*
