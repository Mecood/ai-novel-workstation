# P4: AI 辅助创作系统 — 规格设计

> 设计日期：2026-07-28
> 状态：已评审，待实现
> 负责人：锦言（验收）· 观星（规格）

---

## 一、总览

P0-P3 建好了工具基础设施（引用、图谱、搜索、导出、备份、CLI、3D）。P4 做**AI 辅助创作**——AI 不替你写，但替你看。

三个子方向（P4A/P4B/P4D，P4C 节奏热力较复杂先跳过）：

| 方向 | 做什么 | 写作者的痛 | 复用 |
|------|--------|-----------|------|
| **P4A 智能叙事评审** | 发 N 章给 AI → 结构/节奏/角色三合一报告 | "写到第10章不知道有没有崩" | AnalysisService + ReviewReport |
| **P4B 人物弧线追踪** | 每章提取角色状态变化 → ECharts 数值曲线 | "我配角5章没出场了？" | Characters API + events |
| **P4D 剧情复盘看板** | 主角目标追踪 + 副线健康度 | "她第3章想干什么来着" | StoryEvents + Foreshadowings |

---

## 二、P4A: 智能叙事评审 (Smart Reviewer)

### 后端设计

#### 新端点：`POST /projects/{id}/analysis/smart-review`

```python
# 请求体
{
  "chapter_numbers": [1,2,3,4,5],    # 或 [-1] 表示全部分析
  "aspects": ["structure","pacing","character"]
}
```

#### 服务层：扩建 `analysis_service.py`

```python
# 新增方法
async def run_smart_review(
    db: AsyncSession,
    project: Project,
    chapter_numbers: list[int],
    aspects: list[str],     # ["structure","pacing","character"]
) -> SmartReviewResult:
    """批量分析多章，返回一份整合智能诊断。"""
```

#### 输出结构 (SmartReviewResult)

```python
{
  "analysis_id": "uuid",
  "project_id": "uuid",
  "chapters_analyzed": [1,2,3,4,5],
  "aspects": {
    "structure": {
      "overall_score": 7.5,
      "issues": [
        {
          "severity": "high",           # high | warn | info
          "chapter_number": 3,
          "line_range": "L80-L120",
          "description": "第3章中段过度消息堆积，建议插入一段环境切换",
          "suggestion": "在第80行后添加一段外部环境描写或视角切换"
        }
      ],
      "summary": "整体结构清晰，但中间段有节奏拖沓……"
    },
    "pacing": {
      "curve": [                         # 逐章节奏打分
        {"chapter": 1, "pacing": 8, "tension": 7, "hook": 9},
        {"chapter": 2, "pacing": 6, "tension": 5, "hook": 8},
      ],
      "areas": [
        {"chapter_number": 2, "role": "tension_low",
         "msg": "第2章张力低于最低安全线 5"}
      ]
    },
    "character": {
      "characters_analyzed": ["诺亚", "塞琳"],
      "issues": [
        {"character_name": "阿尔比", "issue": "已连续 4 章未出场"}
      ]
    }
  },
  "suggestions": [                        # 按 urgent 排序
    {"priority": 1, "message": "第3章中段节奏拖沓——考虑合并两段过渡描写"},
    {"priority": 2, "message": "角色「阿尔比」已4章未出场，建议安排回归或交代结果"}
  ]
}
```

#### API 路由

- `POST /analysis/smart-review` — 触发审查任务
- `GET /analysis/smart-review/{analysis_id}` — 获取已完成结果
- `GET /projects/{id}/analysis/smart-reviews` — 历史报告列表

#### 存储：复用 ReviewReport 表

新增字段：`analysis_type` 值设为 `smart_review`，`result` JSON 字段存完整 SmartReviewResult。

---

### 前端设计：SmartReviewPage

**路径**：`frontend/src/pages/project/SmartReviewPage.tsx`

**布局**：

```
┌─ 章节选择 ────────────────────────────────┐
│ [Checkbox: 第1章] [Checkbox: 第2章] ...        │
│ [全选] [最近5章] [最近10章]                  │
│ [选择分析维度: 结构 | 节奏 | 角色] [全面分析] │
├─ 节奏曲线图 ────────────────────────────────┤
│   ECharts 三线 (pacing/tension/hook) × N章    │
├─ 结构问题 ──────────────────────────────────┤
│   问题列表 + 章节跳转链接                      │
├─ 角色状态 ──────────────────────────────────┤
│   角色变化轴 + 缺失警告                        │
├─ 综合建议 ──────────────────────────────────┤
│   按 urgent 排序的行为 check 卡片              │
└──────────────────────────────────────────────┘
```

**路由**：`/project/{id}/smart-review`

---

## 三、P4B: 人物弧线追踪

### 后端设计

**新端点**：`GET /projects/{id}/characters/arc`

```python
# 返回
{
  "characters": [
    {
      "id": "6f45d546-...",
      "name": "诺亚",
      "role_type": "主角",
      "arc": [
        {"chapter": 1, "power": 3, "emotion": 5, "relationship_density": 1},
        {"chapter": 2, "power": 4, "emotion": 3, "relationship_density": 2},
        {"chapter": 3, "power": 5, "emotion": 6, "relationship_density": 3},
      ],
      "issues": [
        {"type": "power_spike", "chapter": 5, "msg": "能力提升过快: 3章内从 3 到 7"},
        {"type": "emotional_flat", "since_chapter": 2, "msg": "情绪 3 章未变"}
      ],
      "last_appearance": 9
    }
  ]
}
```

**新文件**：`backend/app/services/character_arc_service.py`

```python
class CharacterArcService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_arc_data(self, project_id: str) -> list[dict]:
        """遍历所有章节，按 character 提取 appearance 序列，
        从 event 的 confidence/event_type 推断 power/emotion 值。"""
```

**API**：`GET /api/v1/projects/{id}/characters/arc`

### 前端设计

**扩展 ** `CharactersPage.tsx` 加一个新 Tab：

```
[角色卡片] | [弧线图表]
```

或独立页：

```
┌─ 角色下拉选择 ──────────────────────┐
│ [诺亚 ▼] [多角色]                    │
├─ 弧线图 ───────────────────────────┤
│  ECharts 多轴童话 (能力+情绪+关系密度)   │
├─ 弧线完整性检查 ────────────────────┤
│  ✅ 诺亚：能力/情绪正向增长             │
│  ⚠️ 阿尔比：已 3 章未出现 | 建议交代原因│
│  🔴 配角B：S1(L100) 出现了矛盾行为     │
└──────────────────────────────────────┘
```

---

## 四、P4D: 剧情复盘看板

### 后端设计

**新端点**：`GET /projects/{id}/plot/dashboard`

```python
{
  "protagonist_goal_journey": [        # 主角目标追踪
    {"chapter": 1, "goal": "做鱼", "goal_type": "original"},
    {"chapter": 3, "goal": "继承刀匠", "goal_type": "new"},
    {"chapter": 8, "goal": "救阿尔比", "goal_type": "updated"}
  ],
  "subplot_health": [
    {"name": "剑刃支线", "last_chapter": 9, "score": 9, "status": "active"},
    {"name": "复仇线", "last_chapter": 3, "score": 3, "status": "abandoned"}
  ],
  "key_events": [    # 重要事件点
    {"chapter": 5, "event": "诺亚获元戒 (foreshadow closed)"},
    {"chapter": 9, "event": "伊格尼斯中枪 (new plot point)"}
  ]
}
```

#### 后端实现

- 从 `StoryEvent` 表提取时序
- 从 `Foreshadowing` 表提取闭合/展开状态
- 从 `context_service.py` 复用记忆数据
- 目标追踪：多 round LLM 推理 + 加键标注

---

### 前端设计：PlotDashboard

**路径**：`frontend/src/pages/project/PlotDashboardPage.tsx`

```
┌─ 主角目标追踪 ──────────────────────────────────┐
│  ["原始目标"]──→["中途目标"]──→["当前目标"]       │
│  直线        分支        最终？                    │
├─ 副线健康度 ──────────────────────────────────────┤
│  3 条副线用 ECharts 条形图：                      │
│  主返回 |##########| 90%                         │
│  复仇线 |###         | 30%                        │
├─ 关键事件里程碑 ──────────────────────────────────┤
│  按章节排序的事件时间线 + 伏笔计数                  │
└──────────────────────────────────────────────────┘
```

---

## 五、任务拆解（三个并行子代理）

### 子代理 1: P4A 智能叙事评审

**完成**：`SmartReviewPage.tsx` + 后端 `smart_review` endpoint  
**预计**：中等复杂度（前端图表多，后端复用已有 AnalysisService）

### 子代理 2: P4B 人物弧线追踪

**完成**：`character_arc_service.py` + Arc ECharts 图 + `GET /arc`  
**预计**：中低复杂（已有 character API + StoryEvent 数据）

### 子代理 3: P4D 剧情复盘看板

**完成**：`PlotDashboardPage.tsx` + `GET /plot-dashboard`  
**预计**：中（数据聚合较复杂）

---

## 五、验收方案

验证脚本 (14 项)：

```bash
# P4A (4 项)
curl POST /analysis/smart-review → 202 accepted → 触发分析
curl GET /analysis/smart-review/{id} → 含 issues[] + suggestions[] 非空
curl GET /smart-reviews → 返回历史列表
前端页面渲染: ECharts 三线图 + 问题列表

# P4B (4 项)
curl GET /characters/arc → 含 3+ 角色
curl GET /characters/arc → 每个角色 arc 含 5+ 章
前端页面渲染: ECharts 弧线 + 检查报告

# P4D (4 项)
curl GET /plot-dashboard → 含 goal_journey + subplot_health
curl POST /plot-dashboard → 数据是真实时间线
前端页面渲染: 目标追踪 + 副线图表

# 底线
npx tsc --noEmit → 0 错误 ✅
py_compile 全通过 ✅
```