## 2026-05-28 修复记录：SSE流式生成 + 一致性检查

### 问题概述
AI章节生成（生成/重新生成）完成后页面一直显示"正在生成"，无法连续操作；生成内容显示为原始JSON格式（含转义换行符）；一致性检查页面白屏。

### 根因分析
1. **SSE协议格式不一致**：后端 generate 用 `{"event":"chunk", "data":chunk}`，但 sse_starlette 把 event 字段当作SSE event type头，不放在data行里，导致前端从data行永远解析不到done事件，generating/regenerating状态永远为true
2. **AI prompt要求输出JSON**：chapter.yaml让AI返回 `{"title":"...", "content":"..."}`，流式输出直接把JSON字符串推到前端
3. **一致性检查**：后端返回content是JSON字符串，前端未解析；字段名不匹配（AI返回severity，前端用type）
4. **大纲生成max_tokens截断**：默认4096不够大纲JSON（~8300 chars），被截断后JSON解析失败，异常被静默吞掉

### 修复内容（8个文件，+397/-56行）

**1. SSE协议统一（generation.py）**
- generate 和 regenerate 端点改用 `yield {"data": json.dumps({"type":"chunk/done", ...})}`
- 新增 generate_chapter_meta() 方法，生成完后单独调AI生成标题和摘要

**2. AI章节生成改为纯文本（chapter.yaml）**
- prompt不再要求输出JSON，直接输出正文
- 流式完成后异步生成标题和摘要

**3. 前端WritingPage修复**
- accumulated改用useRef避免closure陷阱
- onDone回调自动选中新章节、清空流式区域
- handleRegenerate同步修复SSE格式
- handleSave包装为{text: content}格式
- 章节标题去重

**4. 一致性检查页面修复（ConsistencyPage.tsx）**
- 解析后端返回的JSON字符串
- 字段名对齐：type→severity, related_entity→suggestion
- 严重等级标签对齐S1-S4分级

**5. 大纲生成修复（ai_service.py）**
- max_tokens从默认4096提升到8192
- JSON解析失败抛422而非静默返回空结果

**6. API层统一（api.ts）**
- generateChapter和regenerate统一为type: chunk/done解析
- 新增onDone回调参数

### Git提交
commit: `fix: SSE流式生成全链路修复 + 一致性检查页面修复`
已推送至 origin/main
