## 2026-05-28 功能更新：知识库自动积累 + 大纲编辑模式

### 一、知识库自动积累系统

**设计理念**：知识库不再是手动填写的空壳，而是随创作自动增长的「AI 记忆库」。

**自动提取流程**：
- 生成世界观 → AI 提取世界观知识 → 存入知识库
- 创建角色 → AI 提取角色档案 → 存入知识库
- 生成章节 → AI 提取本章关键设定/事件/地点 → 存入知识库
- 重新生成章节 → 同上

**技术改动**：
- `Knowledge` 模型新增 `source`（manual/auto）、`source_type`、`source_id` 字段
- 新增 `knowledge_extract.yaml` prompt 模板
- `AIService` 新增 `extract_knowledge()` 方法
- `generation.py` 所有生成端点完成后自动调用知识提取
- `search.py` 新增 `knowledge` 索引类型，支持向量检索

**前端改动**：
- 自动条目显示「自动·世界观/角色/章节」标签（青色）
- 自动条目隐藏删除按钮（不可手动删除）
- 手动条目正常显示和操作

### 二、大纲页面增强

**树状图视图**：
- 工具栏新增 Segmented 切换：「表单」/「树状图」
- 树状图展示 Volume → Chapters 层级结构
- 每个节点显示标题和摘要前50字
- 默认全部展开

**编辑模式开关**：
- 工具栏新增 Switch 开关，默认「只读」状态
- 只读模式下：TextArea/Input 用 readOnly（文字颜色正常，可选中复制，不可编辑）
- InputNumber 用 disabled（antd 不支持 readOnly）
- 添加卷/保存/删除按钮在只读模式下不可用
- 开启编辑模式后才可修改

### Git 提交
- commit: `feat: 知识库自动积累 + 大纲编辑模式/树状图`
- 已推送至 origin/main
