"""
合同系统服务 — 写前契约生成/签署 + 写后履行检查/提交判定。

核心流程：
1. sign_contract()    → 写前：LLM 根据大纲细纲+世界观+角色生成契约 → 写入 chapter_contracts
2. check_fulfillment() → 写后：对比正文与契约 → 输出 planned/covered/missed/extra_nodes
3. commit_chapter()   → 汇总审查+履行+提取结果 → 判定 accepted/rejected

依赖：review_reports 表（审查报告，含 blocking_count/issues）
      story_events 表（10 类事件提取）
      Chapter 模型（含 content, summary, outline_detail）
"""
import json
import re
import uuid
from typing import Any
from datetime import datetime, timezone

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import AIService
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.chapter_contract import ChapterContract, ContractStatus
from app.models.chapter_commit import ChapterCommit, CommitStatus
from app.models.contract_audit_log import ContractAuditLog
from app.models.review_report import ReviewReport
from app.models.story_event import StoryEvent


class ContractService:
    """
    合同系统核心服务。
    """

    def __init__(self, ai_service: AIService):
        self._ai_service = ai_service

    # ═══════════════════════════════════════════════════════════════════
    # 公共方法
    # ═══════════════════════════════════════════════════════════════════

    # ── 1) 签署契约 ──────────────────────────────────────────────────────

    async def sign_contract(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict:
        """
        写前签约：根据大纲细纲 + 世界观 + 角色设定，生成契约并写入数据库。

        流程：
        1. 收集上下文：大纲细纲、世界观规则、角色设定、前几章事件
        2. 调 LLM 生成契约内容（required_nodes, optional_nodes, constraints, forbidden_zones）
        3. 如果已有旧契约（status=draft/signed），将其标记为过期（通过覆盖逻辑？
           建议：直接更新现有契约，或删除旧记录）
        4. 写入 chapter_contracts，status=signed

        返回：契约的完整 dict
        """
        # 1) 收集上下文
        context = await self._build_contract_context(db, project, chapter)

        # 2) 调 LLM 生成契约
        contract_data = await self._call_llm_generate_contract(
            db, project, chapter, context
        )

        # 3) 处理已有契约
        existing = await self._get_existing_contract(db, str(project.id), chapter.chapter_number)
        if existing:
            # 更新现有契约
            existing.required_nodes = contract_data.get("required_nodes", [])
            existing.optional_nodes = contract_data.get("optional_nodes", [])
            existing.constraints = contract_data.get("constraints", [])
            existing.forbidden_zones = contract_data.get("forbidden_zones", [])
            existing.context_summary = context.get("summary", "")
            existing.status = ContractStatus.SIGNED.value
            existing.signed_at = datetime.now(timezone.utc)
            existing.chapter_id = chapter.id
            await db.flush()
            await self._log_audit(
                db, str(project.id), chapter.chapter_number,
                "UPDATE", existing,
                old_status=ContractStatus.DRAFT.value,
                new_status=ContractStatus.SIGNED.value,
                old_nodes=contract_data.get("required_nodes", []),
                new_nodes=contract_data.get("required_nodes", []),
                old_zones=contract_data.get("forbidden_zones", []),
                new_zones=contract_data.get("forbidden_zones", []),
                old_constraints=contract_data.get("constraints", []),
                new_constraints=contract_data.get("constraints", []),
                note="重新签署（替换旧契约）",
            )
            return self._contract_to_dict(existing)
        else:
            # 创建新契约
            contract = ChapterContract(
                project_id=project.id,
                chapter_number=chapter.chapter_number,
                chapter_id=chapter.id,
                status=ContractStatus.SIGNED.value,
                required_nodes=contract_data.get("required_nodes", []),
                optional_nodes=contract_data.get("optional_nodes", []),
                constraints=contract_data.get("constraints", []),
                forbidden_zones=contract_data.get("forbidden_zones", []),
                context_summary=context.get("summary", ""),
                signed_at=datetime.now(timezone.utc),
            )
            db.add(contract)
            await db.flush()
            await self._log_audit(
                db, str(project.id), chapter.chapter_number,
                "CREATE", contract,
                old_status=None,
                new_status=ContractStatus.SIGNED.value,
                new_nodes=contract_data.get("required_nodes", []),
                new_zones=contract_data.get("forbidden_zones", []),
                new_constraints=contract_data.get("constraints", []),
                note="新建契约",
            )
            return self._contract_to_dict(contract)

    # ── 2) 获取契约 ──────────────────────────────────────────────────────

    async def get_contract(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
    ) -> dict | None:
        """获取一章的最新契约。"""
        contract = await self._get_existing_contract(db, project_id, chapter_number)
        if not contract:
            return None
        return self._contract_to_dict(contract)

    # ── 3) 检查履行度 ────────────────────────────────────────────────────

    async def check_fulfillment(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        contract: ChapterContract | None = None,
    ) -> dict:
        """
        写后履行检查：对比正文与契约，输出履行结果。

        流程：
        1. 获取契约（如未提供则自动查询）
        2. 调 LLM 分析正文，判断哪些节点被覆盖
        3. 输出结构化的履行结果

        返回：fulfillment_result dict
        """
        if not contract:
            contract = await self._get_existing_contract(
                db, str(project.id), chapter.chapter_number
            )

        if not contract:
            # 没有契约 = 自由写作，返回空履行结果
            return {
                "planned_nodes": [],
                "covered_nodes": [],
                "missed_nodes": [],
                "extra_nodes": [],
                "forbidden_violations": [],
                "summary": "没有签署契约，无法检查履行度",
                "contract_exists": False,
            }

        # 提取正文文本
        text = self._extract_chapter_text(chapter)
        if not text or len(text.strip()) < 50:
            return {
                "planned_nodes": [n.get("id") for n in (contract.required_nodes or [])],
                "covered_nodes": [],
                "missed_nodes": [n.get("id") for n in (contract.required_nodes or [])],
                "extra_nodes": [],
                "forbidden_violations": [],
                "summary": "章节内容过短，无法检查履行度",
                "contract_exists": True,
            }

        # 调 LLM 分析履行度
        fulfillment = await self._call_llm_check_fulfillment(
            db, project, chapter, contract, text
        )

        return fulfillment

    # ── 4) 提交章节 ──────────────────────────────────────────────────────

    async def commit_chapter(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict:
        """
        提交章节：汇总审查结果 + 履行结果 + 提取结果，判定 accepted/rejected。

        判定规则：
        - blocking_count > 0  → REJECTED
        - missed_nodes > 0    → REJECTED
        - 否则                → ACCEPTED

        流程：
        1. 获取该章的审查报告 (review_reports)
        2. 获取该章的契约 + 执行履行检查
        3. 获取该章的事件提取结果 (story_events)
        4. 判定 + 写入 chapter_commits
        5. 更新契约状态 (fulfilled/rejected)
        """
        ch_num = chapter.chapter_number
        project_id_str = str(project.id)

        # 1) 获取审查报告
        review_report = await self._get_review_report(db, project_id_str, ch_num)
        review_result = self._build_review_result(review_report)

        # 2) 获取契约 + 履行检查
        contract = await self._get_existing_contract(db, project_id_str, ch_num)
        if contract and contract.status not in (ContractStatus.SIGNED.value, ContractStatus.FULFILLED.value, ContractStatus.REJECTED.value):
            # 如果契约是 draft 状态，先自动签署
            contract.status = ContractStatus.SIGNED.value
            contract.signed_at = datetime.now(timezone.utc)

        fulfillment_result = await self.check_fulfillment(db, project, chapter, contract)

        # 3) 获取事件提取结果
        extraction_result = await self._get_extraction_result(db, project_id_str, ch_num)

        # 4) 判定
        blocking_count = review_result.get("blocking_count", 0)
        missed_nodes = fulfillment_result.get("missed_nodes", [])
        forbidden_violations = fulfillment_result.get("forbidden_violations", [])

        rejection_reasons = []
        if blocking_count > 0:
            for issue in review_result.get("blocking_issues", []):
                rejection_reasons.append(f"blocking_issue: {issue}")
        if missed_nodes:
            # 从契约中获取节点标题
            node_title_map = {}
            if contract:
                for n in (contract.required_nodes or []):
                    node_title_map[n.get("id")] = n.get("title", n.get("id"))
            for nid in missed_nodes:
                title = node_title_map.get(nid, nid)
                rejection_reasons.append(f"missed_node: {title}")
        if forbidden_violations:
            zone_desc_map = {}
            if contract:
                for z in (contract.forbidden_zones or []):
                    zone_desc_map[z.get("id")] = z.get("description", z.get("id"))
            for zid in forbidden_violations:
                zone_desc = zone_desc_map.get(zid, zid)
                rejection_reasons.append(f"forbidden_violation: {zone_desc}")

        if blocking_count > 0 or len(missed_nodes) > 0:
            commit_status = CommitStatus.REJECTED
            if contract:
                contract.status = ContractStatus.REJECTED.value
        else:
            commit_status = CommitStatus.ACCEPTED
            if contract:
                contract.status = ContractStatus.FULFILLED.value

        # 计算 commit_version
        last_commit = await db.execute(
            select(ChapterCommit)
            .where(
                ChapterCommit.project_id == project_id_str,
                ChapterCommit.chapter_number == ch_num,
            )
            .order_by(desc(ChapterCommit.commit_version))
            .limit(1)
        )
        last = last_commit.scalar_one_or_none()
        next_version = (last.commit_version + 1) if last else 1

        # 5) 写入 chapter_commits
        commit = ChapterCommit(
            project_id=project.id,
            chapter_number=ch_num,
            chapter_id=chapter.id,
            contract_id=contract.id if contract else None,
            status=commit_status.value,
            commit_version=next_version,
            fulfillment_result=fulfillment_result,
            review_result=review_result,
            extraction_result=extraction_result,
            projection_status=None,
            rejection_reasons=rejection_reasons,
        )
        db.add(commit)
        await db.flush()

        # 审计日志
        old_contract_status = contract.status.value if contract else None
        new_contract_status = (ContractStatus.FULFILLED.value if commit_status == CommitStatus.ACCEPTED
                              else ContractStatus.REJECTED.value)
        await self._log_audit(
            db, project_id_str, ch_num,
            "COMMIT", contract,
            old_status=old_contract_status,
            new_status=new_contract_status,
            detail={
                "commit_version": next_version,
                "commit_status": commit_status.value,
                "blocking_count": blocking_count,
                "missed_node_count": len(missed_nodes),
                "forbidden_violation_count": len(forbidden_violations),
                "rejection_reasons": rejection_reasons,
            },
            note=f"章节提交——版本{next_version}——{commit_status.value}",
        )

        return self._commit_to_dict(commit)

    # ── 5) 获取提交记录 ─────────────────────────────────────────────────

    async def get_commit(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
        version: int | None = None,
    ) -> dict | None:
        """获取一章的提交记录，默认取最新版本。"""
        q = select(ChapterCommit).where(
            ChapterCommit.project_id == project_id,
            ChapterCommit.chapter_number == chapter_number,
        )
        if version is not None:
            q = q.where(ChapterCommit.commit_version == version)
        q = q.order_by(desc(ChapterCommit.commit_version)).limit(1)
        result = await db.execute(q)
        commit = result.scalar_one_or_none()
        if not commit:
            return None
        return self._commit_to_dict(commit)

    async def get_commit_history(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
    ) -> list[dict]:
        """获取一章的所有提交历史。"""
        result = await db.execute(
            select(ChapterCommit)
            .where(
                ChapterCommit.project_id == project_id,
                ChapterCommit.chapter_number == chapter_number,
            )
            .order_by(ChapterCommit.commit_version.asc())
        )
        commits = result.scalars().all()
        return [self._commit_to_dict(c) for c in commits]

    # ═══════════════════════════════════════════════════════════════════
    # 私有方法
    # ═══════════════════════════════════════════════════════════════════

    async def _build_contract_context(self, db: AsyncSession, project: Project,
                                       chapter: Chapter) -> dict:
        """
        收集契约生成所需上下文：
        - 项目世界观（worldview rules）
        - 角色设定（characters）
        - 前情摘要（previous chapters summary）
        - 本章大纲细纲（outline_detail）
        - 前几章提取的事件（story_events）
        """
        context = {
            "project_name": project.name,
            "chapter_number": chapter.chapter_number,
            "chapter_title": chapter.title,
        }

        # 世界观
        from app.models.worldview import Worldview
        wv_result = await db.execute(
            select(Worldview).where(Worldview.project_id == project.id)
        )
        worldview = wv_result.scalar_one_or_none()
        if worldview:
            context["worldview"] = {
                "name": worldview.name,
                "description": worldview.description,
                "rules": worldview.rules or [],
            }

        # 角色设定
        from app.models.character import Character
        char_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        chars = char_result.scalars().all()
        context["characters"] = [
            {
                "name": c.name,
                "description": c.description,
                "traits": c.traits or [],
                "aliases": c.aliases or [],
            }
            for c in chars
        ]

        # 本章大纲细纲
        context["outline_detail"] = chapter.outline_detail or {}

        # 前情摘要（前 5 章摘要）
        prev_result = await db.execute(
            select(Chapter)
            .where(
                Chapter.project_id == project.id,
                Chapter.chapter_number < chapter.chapter_number,
                Chapter.chapter_number >= chapter.chapter_number - 5,
            )
            .order_by(Chapter.chapter_number.asc())
        )
        prev_chapters = prev_result.scalars().all()
        context["previous_chapters"] = [
            {
                "chapter_number": c.chapter_number,
                "title": c.title,
                "summary": c.summary,
            }
            for c in prev_chapters
        ]

        # 最近事件（前 3 章的最新事件）
        from app.models.story_event import StoryEvent
        ev_result = await db.execute(
            select(StoryEvent)
            .where(
                StoryEvent.project_id == project.id,
                StoryEvent.chapter_number >= chapter.chapter_number - 3,
                StoryEvent.chapter_number < chapter.chapter_number,
            )
            .order_by(StoryEvent.chapter_number.desc(), StoryEvent.order.desc())
            .limit(20)
        )
        events = ev_result.scalars().all()
        context["recent_events"] = [
            {
                "chapter_number": e.chapter_number,
                "event_type": e.event_type,
                "title": e.title,
            }
            for e in events
        ]

        # 生成摘要（用于调试/审计）
        summary_parts = [
            f"项目：{project.name}",
            f"章节：第{chapter.chapter_number}章 {chapter.title}",
        ]
        if context.get("worldview"):
            summary_parts.append(f"世界观：{context['worldview']['name']}（{len(context['worldview']['rules'])} 条规则）")
        if context.get("characters"):
            summary_parts.append(f"角色：{len(context['characters'])} 个")
        if context.get("outline_detail"):
            summary_parts.append(f"细纲：{json.dumps(context['outline_detail'], ensure_ascii=False)[:200]}")
        context["summary"] = "\n".join(summary_parts)

        return context

    async def _call_llm_generate_contract(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        context: dict,
    ) -> dict:
        """
        调 LLM 生成契约内容。

        输出格式（JSON）：
        {
            "required_nodes": [
                {"id": "node_001", "title": "林动突破地阶", "description": "...", "character": "林动"},
                ...
            ],
            "optional_nodes": [
                {"id": "node_003", "title": "古墓场景描写", "description": "...", "character": null},
                ...
            ],
            "constraints": [
                {"key": "word_count", "label": "字数控制", "value": "2000-3000字"},
                {"key": "perspective", "label": "视角", "value": "林动主视角"},
                ...
            ],
            "forbidden_zones": [
                {"id": "zone_001", "description": "不能提前揭露幕后黑手", "reason": "伏笔设置在第20章回收"},
                ...
            ]
        }
        """
        # 构建 LLM 提示
        system_prompt = (
            "你是一位小说章节契约分析师。你的任务是根据大纲细纲、世界观设定和角色设定，"
            "为即将开始写作的章节生成一份「写作契约」。\n\n"
            "契约包含四部分：\n"
            "1. required_nodes：本章必须覆盖的核心叙事节点（3-6个），每个节点包含 id、title(≤20字)、description(≤100字)、character(关联角色名)\n"
            "2. optional_nodes：可选覆盖的补充节点（0-3个），格式同上\n"
            "3. constraints：写作约束（如字数、视角、风格等），每个包含 key、label、value\n"
            "4. forbidden_zones：本章不能碰的内容禁区，每个包含 id、description、reason\n\n"
            "请严格输出 JSON 对象，不要 markdown 包裹，不要多余文字。"
        )
        user_prompt = (
            f"### 项目名称：{context.get('project_name', '')}\n"
            f"### 章节：第{context.get('chapter_number', '?')}章 {context.get('chapter_title', '')}\n\n"
        )
        if context.get("worldview"):
            user_prompt += (
                f"### 世界观设定：\n{json.dumps(context['worldview'], ensure_ascii=False)[:500]}\n\n"
            )
        if context.get("characters"):
            chars_info = json.dumps(context['characters'], ensure_ascii=False)[:1000]
            user_prompt += f"### 角色设定：\n{chars_info}\n\n"
        if context.get("outline_detail"):
            outline_info = json.dumps(context['outline_detail'], ensure_ascii=False)[:1000]
            user_prompt += f"### 本章细纲：\n{outline_info}\n\n"
        if context.get("previous_chapters"):
            prev_info = json.dumps(context['previous_chapters'], ensure_ascii=False)[:500]
            user_prompt += f"### 前情摘要：\n{prev_info}\n\n"
        if context.get("recent_events"):
            events_info = json.dumps(context['recent_events'], ensure_ascii=False)[:500]
            user_prompt += f"### 最近事件：\n{events_info}\n\n"

        user_prompt += "请生成这份章节的写作契约（JSON格式）："

        client = await self._ai_service._build_client(db)
        try:
            result = str(await client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            ))
            return self._parse_contract_json(result)
        finally:
            await client.close()

    def _parse_contract_json(self, text: str) -> dict:
        """解析 LLM 返回的契约 JSON。"""
        text = re.sub(r"```(?:json)?\s*", "", text)
        # 尝试匹配 JSON 对象
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return self._default_contract()

        try:
            data = json.loads(match.group())
            if not isinstance(data, dict):
                return self._default_contract()
            return {
                "required_nodes": self._validate_nodes(data.get("required_nodes", [])),
                "optional_nodes": self._validate_nodes(data.get("optional_nodes", [])),
                "constraints": self._validate_constraints(data.get("constraints", [])),
                "forbidden_zones": self._validate_zones(data.get("forbidden_zones", [])),
            }
        except Exception:
            return self._default_contract()

    def _default_contract(self) -> dict:
        """LLM 解析失败时的默认契约。"""
        return {
            "required_nodes": [],
            "optional_nodes": [],
            "constraints": [],
            "forbidden_zones": [],
        }

    def _validate_nodes(self, nodes: list) -> list:
        """校验并规范化节点列表。"""
        out = []
        for i, n in enumerate(nodes):
            if not isinstance(n, dict):
                continue
            out.append({
                "id": str(n.get("id", f"node_{i+1:03d}")),
                "title": str(n.get("title", ""))[:50],
                "description": str(n.get("description", ""))[:200],
                "character": str(n.get("character", "")) if n.get("character") else None,
            })
        return out

    def _validate_constraints(self, constraints: list) -> list:
        """校验并规范化约束列表。"""
        out = []
        for c in constraints:
            if not isinstance(c, dict):
                continue
            out.append({
                "key": str(c.get("key", "")),
                "label": str(c.get("label", ""))[:50],
                "value": str(c.get("value", ""))[:200],
            })
        return out

    def _validate_zones(self, zones: list) -> list:
        """校验并规范化禁区列表。"""
        out = []
        for i, z in enumerate(zones):
            if not isinstance(z, dict):
                continue
            out.append({
                "id": str(z.get("id", f"zone_{i+1:03d}")),
                "description": str(z.get("description", ""))[:200],
                "reason": str(z.get("reason", ""))[:200],
            })
        return out

    # ── Audit helpers ────────────────────────────────────────────────

    async def _log_audit(
        self,
        db: AsyncSession,
        project_id: str | uuid.UUID,
        chapter_number: int,
        action: str,
        contract: ChapterContract | None,
        *,
        old_status: str | None = None,
        new_status: str | None = None,
        old_nodes: list | None = None,
        new_nodes: list | None = None,
        old_zones: list | None = None,
        new_zones: list | None = None,
        old_constraints: list | None = None,
        new_constraints: list | None = None,
        detail: dict | None = None,
        note: str | None = None,
        actor: str = "auto_pipeline",
    ) -> None:
        """Append-only 审计日志写入。不修改 contract 本身。"""
        try:
            log = ContractAuditLog(
                project_id=uuid.UUID(project_id) if isinstance(project_id, str) else project_id,
                chapter_number=chapter_number,
                contract_id=contract.id if contract else None,
                action=action,
                actor=actor,
                old_status=old_status,
                old_required_nodes=old_nodes,
                old_forbidden_zones=old_zones,
                old_constraints=old_constraints,
                new_status=new_status,
                new_required_nodes=new_nodes,
                new_forbidden_zones=new_zones,
                new_constraints=new_constraints,
                detail=detail,
                note=note,
            )
            db.add(log)
            await db.flush()
        except Exception:
            # 审计日志写入失败不阻断主流程（降级容忍）
            pass

    async def get_audit_logs(
        self,
        db: AsyncSession,
        project_id: str | uuid.UUID,
        chapter_number: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """获取审计日志。"""
        q = select(ContractAuditLog).where(
            ContractAuditLog.project_id == (
                uuid.UUID(project_id) if isinstance(project_id, str) else project_id
            )
        )
        if chapter_number is not None:
            q = q.where(ContractAuditLog.chapter_number == chapter_number)
        q = q.order_by(ContractAuditLog.created_at.desc()).limit(limit)
        result = await db.execute(q)
        logs = result.scalars().all()
        return [l.to_dict() for l in logs]

    async def _call_llm_check_fulfillment(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        contract: ChapterContract,
        text: str,
    ) -> dict:
        """
        调 LLM 分析正文对契约的履行情况。

        输出格式（JSON）：
        {
            "covered_nodes": ["node_001", "node_003"],
            "extra_nodes": ["node_005"],
            "forbidden_violations": [],
            "summary": "覆盖了 3/4 个核心节点，角色情感弧线完整"
        }
        """
        # 将契约节点组织成描述文本
        required_list = "\n".join(
            f"- [{n.get('id')}] {n.get('title')}：{n.get('description')}"
            for n in (contract.required_nodes or [])
        )
        forbidden_list = "\n".join(
            f"- [{z.get('id')}] {z.get('description')}（原因：{z.get('reason')}）"
            for z in (contract.forbidden_zones or [])
        )
        optional_list = "\n".join(
            f"- [{n.get('id')}] {n.get('title')}：{n.get('description')}"
            for n in (contract.optional_nodes or [])
        )

        system_prompt = (
            "你是一位小说章节履行度审查员。你的任务是判断给定章节正文是否履行了写前契约中承诺的节点。\n\n"
            "请输出 JSON 对象，包含：\n"
            "1. covered_nodes：正文中确实覆盖到的 required_nodes 的 id 列表\n"
            "2. extra_nodes：正文中出现了但契约中未要求的重要内容节点 id 列表（可选，用 new_node_001 等临时 id）\n"
            "3. forbidden_violations：正文中触犯的禁区 id 列表\n"
            "4. summary：一段简短的文字总结（≤100字）\n\n"
            "判定标准：\n"
            "- 如果一个 required_node 在正文中有明确的情节推进或描写，就算覆盖\n"
            "- 如果只是模糊提及但没有实质内容，不算覆盖\n"
            "- 如果正文内容明确违反了 forbidden_zone 的描述，算触犯\n\n"
            "仅输出 JSON 对象，不要 markdown 包裹，不要多余文字。"
        )
        user_prompt = (
            f"### 契约：第{chapter.chapter_number}章\n\n"
            f"【必须覆盖的节点】\n{required_list or '（无）'}\n\n"
            f"【可选节点】\n{optional_list or '（无）'}\n\n"
            f"【禁区】\n{forbidden_list or '（无）'}\n\n"
            f"### 正文（截断到 3000 字）：\n\n{text[:3000]}\n\n"
            "请判断履行情况："
        )

        client = await self._ai_service._build_client(db)
        try:
            result = str(await client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            ))

            # 解析
            result_clean = re.sub(r"```(?:json)?\s*", "", result)
            match = re.search(r"\{.*\}", result_clean, re.DOTALL)
            if not match:
                return self._empty_fulfillment(contract)

            data = json.loads(match.group())
            required_ids = [n.get("id") for n in (contract.required_nodes or [])]

            covered = data.get("covered_nodes", [])
            if not isinstance(covered, list):
                covered = []

            forbidden_violations = data.get("forbidden_violations", [])
            if not isinstance(forbidden_violations, list):
                forbidden_violations = []

            extra = data.get("extra_nodes", [])
            if not isinstance(extra, list):
                extra = []

            missed = [nid for nid in required_ids if nid not in covered]

            return {
                "planned_nodes": required_ids,
                "covered_nodes": covered,
                "missed_nodes": missed,
                "extra_nodes": extra,
                "forbidden_violations": forbidden_violations,
                "summary": str(data.get("summary", ""))[:200],
                "contract_exists": True,
            }
        except Exception:
            return self._empty_fulfillment(contract)
        finally:
            await client.close()

    def _empty_fulfillment(self, contract: ChapterContract | None) -> dict:
        """LLM 分析失败时的默认履行结果。"""
        if contract:
            required_ids = [n.get("id") for n in (contract.required_nodes or [])]
            return {
                "planned_nodes": required_ids,
                "covered_nodes": [],
                "missed_nodes": required_ids,
                "extra_nodes": [],
                "forbidden_violations": [],
                "summary": "履行检查分析失败，所有节点标记为未覆盖",
                "contract_exists": True,
            }
        return {
            "planned_nodes": [],
            "covered_nodes": [],
            "missed_nodes": [],
            "extra_nodes": [],
            "forbidden_violations": [],
            "summary": "没有签署契约",
            "contract_exists": False,
        }

    # ── 辅助查询方法 ────────────────────────────────────────────────────

    async def _get_existing_contract(
        self, db: AsyncSession, project_id: str, chapter_number: int
    ) -> ChapterContract | None:
        """获取一章最新契约（优先 signed 状态，回退到 draft）。"""
        result = await db.execute(
            select(ChapterContract)
            .where(
                ChapterContract.project_id == project_id,
                ChapterContract.chapter_number == chapter_number,
            )
            .order_by(desc(ChapterContract.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_review_report(
        self, db: AsyncSession, project_id: str, chapter_number: int
    ) -> ReviewReport | None:
        """获取一章的最新审查报告。"""
        result = await db.execute(
            select(ReviewReport)
            .where(
                ReviewReport.project_id == project_id,
                ReviewReport.chapter_number == chapter_number,
            )
            .order_by(desc(ReviewReport.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_extraction_result(
        self, db: AsyncSession, project_id: str, chapter_number: int
    ) -> dict:
        """获取一章的事件提取结果摘要。"""
        result = await db.execute(
            select(StoryEvent)
            .where(
                StoryEvent.project_id == project_id,
                StoryEvent.chapter_number == chapter_number,
            )
        )
        events = result.scalars().all()
        return {
            "event_count": len(events),
            "event_types": list(set(e.event_type for e in events)),
            "events_extracted": len(events) > 0,
        }

    def _build_review_result(self, report: ReviewReport | None) -> dict:
        """从 ReviewReport 构建 review_result 结构。"""
        if not report:
            return {
                "report_id": None,
                "overall_score": None,
                "blocking_count": 0,
                "blocking_issues": [],
                "dimension_scores": {},
            }
        blocking_issues = [
            i.get("description", "未知阻断问题")
            for i in (report.issues or [])
            if i.get("blocking", False)
        ]
        return {
            "report_id": str(report.id),
            "overall_score": float(report.overall_score) if report.overall_score is not None else None,
            "blocking_count": report.blocking_count or 0,
            "blocking_issues": blocking_issues,
            "dimension_scores": report.dimension_scores or {},
        }

    # ── 序列化方法 ──────────────────────────────────────────────────────

    def _contract_to_dict(self, c: ChapterContract) -> dict:
        return {
            "id": str(c.id),
            "project_id": str(c.project_id),
            "chapter_number": c.chapter_number,
            "chapter_id": str(c.chapter_id) if c.chapter_id else None,
            "status": c.status,
            "required_nodes": c.required_nodes or [],
            "optional_nodes": c.optional_nodes or [],
            "constraints": c.constraints or [],
            "forbidden_zones": c.forbidden_zones or [],
            "context_summary": c.context_summary or "",
            "signed_at": c.signed_at.isoformat() if c.signed_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }

    def _commit_to_dict(self, c: ChapterCommit) -> dict:
        return {
            "id": str(c.id),
            "project_id": str(c.project_id),
            "chapter_number": c.chapter_number,
            "chapter_id": str(c.chapter_id) if c.chapter_id else None,
            "contract_id": str(c.contract_id) if c.contract_id else None,
            "status": c.status,
            "commit_version": c.commit_version,
            "fulfillment_result": c.fulfillment_result or {},
            "review_result": c.review_result or {},
            "extraction_result": c.extraction_result or {},
            "projection_status": c.projection_status,
            "rejection_reasons": c.rejection_reasons or [],
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }

    def _extract_chapter_text(self, chapter: Chapter) -> str:
        """从 Chapter 对象提取纯文本正文。"""
        if isinstance(chapter.content, dict):
            return chapter.content.get("text", json.dumps(chapter.content, ensure_ascii=False))
        if isinstance(chapter.content, str):
            return chapter.content
        return str(chapter.content or "")