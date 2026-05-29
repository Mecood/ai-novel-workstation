# 版本管理 + 级联失效 实施计划

## 核心思路
每个生成节点有 version + based_on + history，用于版本管理和级联失效检测。

## 数据结构（存在节点的JSON字段里，不新增表）

### Story Core（存在Project.story_core JSON里）
```json
{
  "_version": 3,
  "_based_on": {},
  "_history": [
    {
      "version": 1,
      "created_at": "2026-05-29T10:00:00",
      "data": { "core_conflict": "...", "theme": "..." }
    }
  ],
  "core_conflict": "...",
  "theme": "...",
  ...
}
```

### Worldview / Character / Chapter / Volume / Outline
每个表新增3个字段：
- `_version` (Integer, default=0) — 节点版本号
- `_based_on` (JSON, default={}) — 基于上游节点的版本号
- `_history` (JSON, default=[]) — 历史版本快照
- `_stale` (Boolean, default=false) — 上游已变化，数据可能不一致

### _based_on 格式
```json
{ "story_core": 2, "worldview": 1, "characters": 1 }
```

### _history 格式
```json
[
  {
    "version": 1,
    "created_at": "2026-05-29T10:00:00",
    "based_on": { "story_core": 1 },
    "data": { "name": "...", "description": "..." }  // 完整节点数据快照
  }
]
```

## 依赖链
```
story_core → worldview
story_core → characters
story_core + worldview + characters → outline(volumes+chapters)
```

## 级联失效逻辑
当节点A被重新生成（version++）时：
1. 检查所有下游节点的 `_based_on` 是否包含对A的引用
2. 如果 `_based_on[A_name]` < A的当前 `_version`，标记为 `_stale=true`
3. 递归传播（如果世界观stale了，基于世界观的章节也要stale）

具体实现用简单遍历，不做复杂依赖图：
- 重新生成 story_core → 标记所有 worldview/character/volume/chapter 为 stale
- 重新生成 worldview → 标记所有 volume/chapter 为 stale
- 重新生成 characters → 标记所有 volume/chapter 为 stale
- 重新生成 outline → 只标记当前章节

## 版本回退逻辑
POST /{node}/restore/{version}
1. 从 _history 中找到对应版本
2. 用该版本的 data 覆盖当前数据
3. 保留当前版本的history（回退也是一种新版本）
4. 更新 _stale=false

## 实施步骤

### Step 1: Model 改动
文件：`backend/app/models/worldview.py`, `character.py`, `chapter.py`, `volume.py`

每个表新增4个字段：
```python
_version = Column(Integer, default=0)
_based_on = Column(JSON, default={})
_history = Column(JSON, default=[])
_stale = Column(Boolean, default=False)
```

### Step 2: Project模型改动
文件：`backend/app/models/project.py`

不需要新增字段，story_core 的版本信息存在 story_core JSON 内部。
但需要新增一个辅助方法或在逻辑里处理。

### Step 3: 数据库迁移
手动 ALTER TABLE，新增4个字段。

### Step 4: Backend - 版本管理服务
新建文件：`backend/app/services/version_service.py`

提供：
- `save_snapshot(node, data, based_on)` — 保存旧版本到history，递增version
- `mark_stale_downstream(project_id, source_name, new_version)` — 标记下游stale
- `restore_version(node, version)` — 回退到指定版本
- `get_upstream_versions(db, project_id)` — 获取当前所有上游节点的版本号

### Step 5: Backend - 修改所有generate端点
在每个generate端点的生成逻辑前后加入版本管理：
1. 生成前：save_snapshot 保存旧数据
2. 生成后：递增version，写入based_on，标记下游stale

涉及文件：
- `backend/app/api/v1/generation.py` (story_core, worldview, characters, outline, chapter generate+regenerate)
- `backend/app/api/v1/story_core.py` (generate端点，同上)

### Step 6: Backend - 新增版本回退API
文件：`backend/app/services/version_service.py`（已有）
在各路由文件中新增 restore 端点

### Step 7: Frontend - 版本历史UI
每个节点页面添加：
- 版本历史下拉/列表
- 过期提示横幅（黄色警告条）
- 回退按钮

涉及文件：
- `frontend/src/pages/project/StoryCorePage.tsx`
- `frontend/src/pages/project/WorldviewPage.tsx`
- `frontend/src/pages/project/CharactersPage.tsx`
- `frontend/src/pages/project/OutlinePage.tsx`

### Step 8: Frontend - API更新
文件：`frontend/src/services/api.ts`
新增 restore API 调用和版本字段类型
