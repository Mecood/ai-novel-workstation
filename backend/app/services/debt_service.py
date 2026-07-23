"""
追读力债务服务 — 评估章节追读力、管理债务生命周期、利息计算与偿还。
"""
import json
import re
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.ai_service import AIService
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.chase_debt import ChaseDebt, DebtType, DebtStatus
from app.models.debt_event import DebtEvent, DebtEventType
from app.models.reading_power import ChapterReadingPower, HookType, HookStrength
from app.models.override_contract import OverrideContract, ConstraintType, RationaleType, ContractStatus


class DebtService:
    """
    追读力债务系统核心服务。

    核心流程：
    1. 章节生成后 → evaluate_chapter_reading_power() → 评估追读力
    2. 追读力不足 → create_debt() → 产生债务
    3. 每章触发 → accrue_interest() → 所有 active 债务计息
    4. 追读力足够高 → pay_debt() → 自动偿还
    5. 到截止日 → check_overdue() → 标记逾期
    """

    READING_POWER_THRESHOLD = Decimal("6.0")        # 追读力合格线
    HIGH_READING_POWER_THRESHOLD = Decimal("8.0")   # 高追读力（触发偿还）
    DEFAULT_INTEREST_RATE = Decimal("0.10")          # 默认利息率 10%
    TRANSITION_DEBT_MULTIPLIER = Decimal("0.5")      # 过渡章债务乘数（减半）

    def __init__(self, ai_service: AIService):
        self._ai_service = ai_service

    # ── 核心方法 ────────────────────────────────────────────────────────

    async def create_debt(
        self,
        db: AsyncSession,
        project_id: str,
        debt_type: DebtType,
        source_chapter: int,
        original_amount: Decimal,
        *,
        description: str | None = None,
        interest_rate: Decimal | None = None,
        due_chapter: int | None = None,
        contract_id: str | None = None,
        metadata: dict | None = None,
    ) -> ChaseDebt:
        """
        创建一笔债务。

        参数：
        - debt_type: 债务类型（hook_strength / micropayoff / coolpoint / reading_desire）
        - source_chapter: 产生债务的章节号
        - original_amount: 初始债务量（0~10）
        - interest_rate: 利息率（默认 10%/章）
        - due_chapter: 截止章节号（可选）
        - contract_id: 关联的 Override Contract ID（可选）
        - description: 债务描述

        返回：ChaseDebt 实例
        """
        # 债务量不能为负
        if original_amount <= 0:
            raise ValueError("original_amount must be positive")

        debt = ChaseDebt(
            project_id=project_id,
            debt_type=debt_type.value,
            description=description or f"第{source_chapter}章 {debt_type.value} 债务 ({original_amount:.1f})",
            original_amount=original_amount,
            current_amount=original_amount,
            interest_rate=interest_rate or self.DEFAULT_INTEREST_RATE,
            source_chapter=source_chapter,
            due_chapter=due_chapter,
            status=DebtStatus.ACTIVE.value,
            contract_id=contract_id,
            metadata=metadata or {},
        )
        db.add(debt)
        await db.flush()  # 拿到 ID

        # 写债务事件日志
        event = DebtEvent(
            debt_id=debt.id,
            project_id=project_id,
            event_type=DebtEventType.CREATED.value,
            chapter_number=source_chapter,
            amount_before=Decimal("0.0"),
            amount_after=original_amount,
            amount_change=original_amount,
            description=description or f"创建债务：{debt_type.value} ({original_amount:.1f})",
        )
        db.add(event)

        return debt

    async def accrue_interest(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
    ) -> int:
        """
        遍历所有 status='active' 的债务，按 interest_rate 计息。
        参数 chapter_number 为当前章节号（用于日志记录）。

        返回：被计息的债务数量
        """
        # 查询所有 active 债务
        result = await db.execute(
            select(ChaseDebt).where(
                ChaseDebt.project_id == project_id,
                ChaseDebt.status == DebtStatus.ACTIVE.value,
            )
        )
        debts = result.scalars().all()

        if not debts:
            return 0

        count = 0
        for debt in debts:
            old_amount = debt.current_amount
            # 计息：current_amount = current_amount * (1 + interest_rate)
            new_amount = old_amount * (Decimal("1.0") + debt.interest_rate)
            # 保留两位小数
            new_amount = Decimal(str(round(float(new_amount), 2)))
            debt.current_amount = new_amount

            # 写日志
            event = DebtEvent(
                debt_id=debt.id,
                project_id=project_id,
                event_type=DebtEventType.INTEREST_ACCRUED.value,
                chapter_number=chapter_number,
                amount_before=old_amount,
                amount_after=new_amount,
                amount_change=new_amount - old_amount,
                description=f"利息累积：{old_amount:.2f} → {new_amount:.2f} (+{debt.interest_rate * 100:.0f}%)",
            )
            db.add(event)
            count += 1

        return count

    async def pay_debt(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
        payment_amount: Decimal,
        *,
        debt_id: str | None = None,
        debt_type: DebtType | None = None,
    ) -> list[dict]:
        """
        偿还债务。

        参数：
        - payment_amount: 偿还总额
        - debt_id: 指定偿还某笔债务（None 则按创建时间顺序偿还最旧的 active 债务）
        - debt_type: 指定偿还某类债务（None 则偿还所有类型）

        偿还规则：
        - 按 created_at 升序（最早的先还）
        - 部分偿还标记为 PARTIAL，全额标记为 PAID
        - 同笔债务可分多次偿还

        返回：本次偿还的债务事件列表
        """
        if payment_amount <= 0:
            return []

        # 构建查询
        q = select(ChaseDebt).where(
            ChaseDebt.project_id == project_id,
            ChaseDebt.status.in_([DebtStatus.ACTIVE.value, DebtStatus.PARTIAL.value]),
        )
        if debt_id:
            q = q.where(ChaseDebt.id == debt_id)
        if debt_type:
            q = q.where(ChaseDebt.debt_type == debt_type.value)
        q = q.order_by(ChaseDebt.created_at.asc())  # 最早的先还

        result = await db.execute(q)
        debts = result.scalars().all()

        if not debts:
            return []

        remaining = payment_amount
        events = []

        for debt in debts:
            if remaining <= 0:
                break

            old_amount = debt.current_amount
            if remaining >= old_amount:
                # 全额偿还
                change = -old_amount
                debt.current_amount = Decimal("0.0")
                debt.status = DebtStatus.PAID.value
                debt.paid_chapter = chapter_number
                event_type = DebtEventType.FULL_PAYMENT.value
                desc = f"全额偿还：{old_amount:.2f}（第{chapter_number}章）"
            else:
                # 部分偿还
                change = -remaining
                debt.current_amount = old_amount - remaining
                debt.status = DebtStatus.PARTIAL.value
                event_type = DebtEventType.PARTIAL_PAYMENT.value
                desc = f"部分偿还：{remaining:.2f}（剩余{debt.current_amount:.2f}）"

            remaining += change  # 因为 change 是负数

            event = DebtEvent(
                debt_id=debt.id,
                project_id=project_id,
                event_type=event_type,
                chapter_number=chapter_number,
                amount_before=old_amount,
                amount_after=debt.current_amount,
                amount_change=change,
                description=desc,
            )
            db.add(event)
            events.append(self._debt_event_to_dict(event))

        return events

    async def check_overdue(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
    ) -> list[dict]:
        """
        检查所有 pending 的 Override Contract 是否到期。
        到期标记为 overdue，同时关联的债务也标记为 overdue。

        返回：本次逾期的合同列表
        """
        # 查找所有 pending 且 due_chapter <= chapter_number 的合同
        result = await db.execute(
            select(OverrideContract).where(
                OverrideContract.project_id == project_id,
                OverrideContract.status == ContractStatus.PENDING.value,
                OverrideContract.due_chapter <= chapter_number,
            )
        )
        contracts = result.scalars().all()

        overdue = []
        for contract in contracts:
            if contract.auto_extend:
                # 自动延期 5 章
                contract.due_chapter = chapter_number + 5
                contract.status = ContractStatus.PENDING.value
            else:
                contract.status = ContractStatus.OVERDUE.value

            # 关联的债务也标记逾期
            debt_result = await db.execute(
                select(ChaseDebt).where(
                    ChaseDebt.contract_id == contract.id,
                    ChaseDebt.status == DebtStatus.ACTIVE.value,
                )
            )
            debts = debt_result.scalars().all()
            for debt in debts:
                debt.status = DebtStatus.OVERDUE.value
                event = DebtEvent(
                    debt_id=debt.id,
                    project_id=project_id,
                    event_type=DebtEventType.OVERDUE.value,
                    chapter_number=chapter_number,
                    amount_before=debt.current_amount,
                    amount_after=debt.current_amount,
                    amount_change=Decimal("0.0"),
                    description=f"逾期（合同到期第{contract.due_chapter}章未履行）",
                )
                db.add(event)

            overdue.append(self._contract_to_dict(contract))

        return overdue

    async def evaluate_chapter_reading_power(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        *,
        content: str | None = None,
    ) -> dict:
        """
        评估单章追读力（核心方法，LLM 调用）。

        流程：
        1. 取章节正文
        2. 调 LLM 按 reading-power-taxonomy 评估
        3. 解析 LLM 返回的 JSON
        4. 写入 chapter_reading_power 表
        5. 若追读力不足，自动创建债务
        6. 若追读力足够高，自动偿还债务
        7. 返回评估结果摘要

        返回：{
            "reading_power_score": float,
            "hook_type": str,
            "hook_strength": str,
            "hook_description": str | None,
            "coolpoint_patterns": list[str],
            "micropayoffs": list[str],
            "is_transition": bool,
            "transition_note": str | None,
            "debt_created": bool,
            "debt_id": str | None,
            "debt_amount": float | None,
            "payment_made": bool,
            "payment_amount": float | None,
        }
        """
        # 1) 取正文
        text = content or self._extract_chapter_text(chapter)
        if not text or len(text.strip()) < 50:
            # 正文过短，写一个默认记录
            rp = await self._save_reading_power(
                db, project.id, chapter.chapter_number,
                score=Decimal("5.0"),
                hook_type=HookType.NONE.value,
                hook_strength=HookStrength.WEAK.value,
                coolpoint_patterns=[],
                micropayoffs=[],
                is_transition=False,
                evaluation_raw=None,
            )
            return {"reading_power_score": 5.0, "debt_created": False,
                    "payment_made": False, "message": "章节内容过短，跳过评估"}

        # 2) 调 LLM 评估
        evaluation = await self._call_llm_evaluate(db, project, chapter.chapter_number, text)

        # 3) 解析结果
        score = Decimal(str(evaluation.get("reading_power_score", 5.0)))
        hook_type = evaluation.get("hook_type", HookType.NONE.value)
        hook_strength = evaluation.get("hook_strength", HookStrength.WEAK.value)
        hook_description = evaluation.get("hook_description")
        coolpoint_patterns = evaluation.get("coolpoint_patterns", [])
        micropayoffs = evaluation.get("micropayoffs", [])
        is_transition = evaluation.get("is_transition", False)
        transition_note = evaluation.get("transition_note")

        # 4) 写入 reading_power 表
        rp = await self._save_reading_power(
            db, project.id, chapter.chapter_number,
            score=score, hook_type=hook_type, hook_strength=hook_strength,
            hook_description=hook_description,
            coolpoint_patterns=coolpoint_patterns,
            micropayoffs=micropayoffs,
            is_transition=is_transition,
            transition_note=transition_note,
            evaluation_raw=evaluation,
        )

        result = {
            "reading_power_id": str(rp.id),
            "reading_power_score": float(score),
            "hook_type": hook_type,
            "hook_strength": hook_strength,
            "hook_description": hook_description,
            "coolpoint_patterns": coolpoint_patterns,
            "micropayoffs": micropayoffs,
            "is_transition": is_transition,
            "transition_note": transition_note,
            "debt_created": False,
            "debt_id": None,
            "debt_amount": None,
            "payment_made": False,
            "payment_amount": None,
        }

        # 5) 债务自动处理
        if score < self.READING_POWER_THRESHOLD:
            # 追读力不足，创建债务
            shortage = Decimal("10.0") - score
            if is_transition:
                # 过渡章债务减半
                shortage = shortage * self.TRANSITION_DEBT_MULTIPLIER

            # 判断债务类型
            if hook_strength == HookStrength.WEAK.value or not hook_description:
                debt_type = DebtType.HOOK_STRENGTH
            elif len(coolpoint_patterns) < 1:
                debt_type = DebtType.COOLPOINT
            elif len(micropayoffs) < 1:
                debt_type = DebtType.MICROPAYOFF
            else:
                debt_type = DebtType.READING_DESIRE

            debt = await self.create_debt(
                db, project.id, debt_type, chapter.chapter_number,
                shortage,
                description=f"第{chapter.chapter_number}章追读力不足 ({float(score):.1f}/10)",
                due_chapter=chapter.chapter_number + 5,  # 默认 5 章内偿还
            )

            # 更新 reading_power 的 debt_balance
            rp.debt_balance = debt.current_amount
            result["debt_created"] = True
            result["debt_id"] = str(debt.id)
            result["debt_amount"] = float(shortage)

        elif score >= self.HIGH_READING_POWER_THRESHOLD:
            # 追读力高，尝试偿还债务
            surplus = score - Decimal("7.0")
            payment_amount = surplus * Decimal("2.0")  # 超过 7.0 的部分双倍偿还能力
            payment_amount = Decimal(str(round(float(payment_amount), 2)))

            if payment_amount > 0:
                events = await self.pay_debt(db, project.id, chapter.chapter_number, payment_amount)
                if events:
                    result["payment_made"] = True
                    result["payment_amount"] = float(payment_amount)

            # 更新债务余额
            total_active = await self._get_active_debt_total(db, project.id)
            rp.debt_balance = total_active

        return result

    async def get_debt_summary(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> dict:
        """
        债务总览（用于 Dashboard）。

        返回：{
            "active_count": int,
            "active_total": float,
            "overdue_count": int,
            "overdue_total": float,
            "paid_count": int,
            "paid_total": float,
            "total_interest_accrued": float,
            "total_original": float,
            "debts": [dict],
            "trend": { ... },
        }
        """
        # 统计各类债务
        result = await db.execute(
            select(
                ChaseDebt.status,
                func.count().label("count"),
                func.coalesce(func.sum(ChaseDebt.current_amount), 0).label("total"),
            ).where(
                ChaseDebt.project_id == project_id,
            ).group_by(ChaseDebt.status)
        )
        rows = result.all()

        # 构造摘要
        active_count = 0
        active_total = 0.0
        overdue_count = 0
        overdue_total = 0.0
        paid_count = 0
        paid_total = 0.0
        total_interest = 0.0
        total_original = 0.0

        for row in rows:
            s = row.status
            c = int(row.count)
            t = float(row.total)
            if s in (DebtStatus.ACTIVE.value, DebtStatus.PARTIAL.value):
                active_count += c
                active_total += t
            elif s == DebtStatus.OVERDUE.value:
                overdue_count += c
                overdue_total += t
            elif s == DebtStatus.PAID.value:
                paid_count += c
                paid_total += t

        # 计算累计利息和初始总额
        all_debt_result = await db.execute(
            select(ChaseDebt).where(ChaseDebt.project_id == project_id)
        )
        all_debts = all_debt_result.scalars().all()
        for d in all_debts:
            total_original += float(d.original_amount)
            total_interest += float(d.current_amount) - float(d.original_amount)

        # 所有债务详情
        debts_list = [self._debt_to_dict(d) for d in all_debts]

        # 趋势数据
        trend = await self.get_reading_power_trend(db, project_id)

        return {
            "active_count": active_count,
            "active_total": round(active_total, 2),
            "overdue_count": overdue_count,
            "overdue_total": round(overdue_total, 2),
            "paid_count": paid_count,
            "paid_total": round(paid_total, 2),
            "total_interest_accrued": round(max(0, total_interest), 2),
            "total_original": round(total_original, 2),
            "debts": debts_list,
            "trend": trend,
        }

    # ── 辅助方法 ───────────────────────────────────────────────────────

    async def get_chapter_reading_power(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
    ) -> dict | None:
        """获取单章追读力元数据。"""
        result = await db.execute(
            select(ChapterReadingPower).where(
                ChapterReadingPower.project_id == project_id,
                ChapterReadingPower.chapter_number == chapter_number,
            )
        )
        rp = result.scalar_one_or_none()
        if not rp:
            return None
        return {
            "id": str(rp.id),
            "project_id": str(rp.project_id),
            "chapter_number": rp.chapter_number,
            "reading_power_score": float(rp.reading_power_score),
            "hook_type": rp.hook_type,
            "hook_strength": rp.hook_strength,
            "hook_description": rp.hook_description,
            "coolpoint_patterns": rp.coolpoint_patterns or [],
            "micropayoffs": rp.micropayoffs or [],
            "is_transition": rp.is_transition,
            "transition_note": rp.transition_note,
            "debt_balance": float(rp.debt_balance) if rp.debt_balance else 0.0,
            "created_at": rp.created_at.isoformat() if rp.created_at else None,
        }

    async def get_reading_power_trend(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> dict:
        """获取追读力趋势数据。"""
        result = await db.execute(
            select(ChapterReadingPower).where(
                ChapterReadingPower.project_id == project_id,
            ).order_by(ChapterReadingPower.chapter_number.asc())
        )
        items = result.scalars().all()

        return {
            "chapters": [rp.chapter_number for rp in items],
            "scores": [float(rp.reading_power_score) for rp in items],
            "hook_strengths": [rp.hook_strength for rp in items],
            "is_transition": [rp.is_transition for rp in items],
            "debt_balances": [float(rp.debt_balance) if rp.debt_balance else 0.0 for rp in items],
        }

    async def get_contracts(
        self,
        db: AsyncSession,
        project_id: str,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """获取 Override Contract 列表。"""
        q = select(OverrideContract).where(OverrideContract.project_id == project_id)
        if status:
            q = q.where(OverrideContract.status == status)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        items_q = q.order_by(OverrideContract.chapter_number.desc()).offset(offset).limit(limit)
        items = (await db.execute(items_q)).scalars().all()

        return {
            "items": [self._contract_to_dict(c) for c in items],
            "total": int(total),
        }

    async def create_contract(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
        constraint_type: ConstraintType,
        rationale_type: RationaleType,
        rationale_text: str,
        due_chapter: int,
        *,
        payback_plan: str | None = None,
        auto_extend: bool = False,
    ) -> OverrideContract:
        """创建 Override Contract。"""
        contract = OverrideContract(
            project_id=project_id,
            chapter_number=chapter_number,
            constraint_type=constraint_type.value,
            rationale_type=rationale_type.value,
            rationale_text=rationale_text,
            payback_plan=payback_plan,
            due_chapter=due_chapter,
            auto_extend=auto_extend,
            status=ContractStatus.PENDING.value,
        )
        db.add(contract)
        await db.flush()
        return contract

    # ── LLM 调用 ───────────────────────────────────────────────────────

    async def _call_llm_evaluate(
        self,
        db: AsyncSession,
        project: Project,
        chapter_number: int,
        text: str,
    ) -> dict:
        """
        调 LLM 按 reading-power-taxonomy 评估章节追读力。
        返回结构化 JSON。
        """
        system_prompt = (
            "你是一位网文追读力分析师。请分析章节正文的追读力（读者继续阅读的欲望强度），"
            "输出严格的 JSON 对象。\n\n"
            "### 评估维度：\n"
            "1. reading_power_score（0-10）：综合追读力评分\n"
            "   - 8-10：强烈追读欲望，章末钩子极强，读者无法停止\n"
            "   - 6-7.9：合格，有继续阅读的欲望但不强烈\n"
            "   - 4-5.9：不足，章末钩子弱，容易弃书\n"
            "   - 0-3.9：严重不足，读者可能直接弃书\n\n"
            "2. hook_type：章末钩子类型\n"
            "   - cliffhanger：悬念断章（\"他推开门，看到了……\"）\n"
            "   - question：疑问断章（\"那个人到底是谁？\"）\n"
            "   - revelation：反转/揭示（\"原来真相是……\"）\n"
            "   - crisis：危机降临（\"一把剑已经刺到眼前\"）\n"
            "   - emotional：情感冲击（\"她转身离去，再也没有回头\"）\n"
            "   - action：战斗高潮\n"
            "   - promise：预告（\"三天后，决战之巅\"）\n"
            "   - none：无钩子\n\n"
            "3. hook_strength：钩子强度（strong / medium / weak）\n"
            "4. hook_description：一句话描述章末钩子（如无则 null）\n"
            "5. coolpoint_patterns：本章出现的爽点模式列表（如 [\"战斗突破\", \"仇人吃瘪\", \"获得宝物\"]）\n"
            "6. micropayoffs：微兑现列表（如 [\"小伏笔回收\", \"对话透露信息\"]）\n"
            "7. is_transition：是否为过渡章（true/false）\n"
            "8. transition_note：如果是过渡章，说明为什么需要过渡（否则 null）\n\n"
            "仅输出 JSON 对象，不要 markdown 包裹，不要多余文字。\n"
            "示例输出：\n"
            '{"reading_power_score": 7.5, "hook_type": "cliffhanger", '
            '"hook_strength": "strong", "hook_description": "主角推开秘境大门，'
            '门后竟站着早已死去的师父", "coolpoint_patterns": ["秘境探索", "身份反转"], '
            '"micropayoffs": ["前文埋下的玉佩伏笔在本章揭示"]'
            ', "is_transition": false, "transition_note": null}'
        )
        user_prompt = (
            f"### 小说名称：{project.name}\n"
            f"### 第 {chapter_number} 章正文（截断到 3000 字）：\n\n"
            f"{text[:3000]}\n\n"
            "请评估本章追读力："
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
            return self._parse_llm_evaluation(result)
        finally:
            await client.close()

    def _parse_llm_evaluation(self, text: str) -> dict:
        text = re.sub(r"```(?:json)?\s*", "", text)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return self._default_evaluation()
        try:
            data = json.loads(match.group())
            if not isinstance(data, dict):
                return self._default_evaluation()
            return {
                "reading_power_score": min(10.0, max(0.0, float(data.get("reading_power_score", 5.0)))),
                "hook_type": data.get("hook_type", "none") if data.get("hook_type") in [
                    "cliffhanger", "question", "revelation", "crisis",
                    "emotional", "action", "promise", "none",
                ] else "none",
                "hook_strength": data.get("hook_strength", "weak") if data.get("hook_strength") in [
                    "strong", "medium", "weak",
                ] else "weak",
                "hook_description": data.get("hook_description"),
                "coolpoint_patterns": data.get("coolpoint_patterns") or [],
                "micropayoffs": data.get("micropayoffs") or [],
                "is_transition": bool(data.get("is_transition", False)),
                "transition_note": data.get("transition_note"),
            }
        except Exception:
            return self._default_evaluation()

    def _default_evaluation(self) -> dict:
        return {
            "reading_power_score": 5.0,
            "hook_type": "none",
            "hook_strength": "weak",
            "hook_description": None,
            "coolpoint_patterns": [],
            "micropayoffs": [],
            "is_transition": False,
            "transition_note": None,
        }

    # ── 内部辅助 ───────────────────────────────────────────────────────

    async def _save_reading_power(
        self, db: AsyncSession, project_id: str, chapter_number: int,
        score: Decimal, hook_type: str, hook_strength: str,
        hook_description: str | None = None,
        coolpoint_patterns: list | None = None,
        micropayoffs: list | None = None,
        is_transition: bool = False,
        transition_note: str | None = None,
        evaluation_raw: dict | None = None,
    ) -> ChapterReadingPower:
        # 检查是否已有记录（幂等）
        result = await db.execute(
            select(ChapterReadingPower).where(
                ChapterReadingPower.project_id == project_id,
                ChapterReadingPower.chapter_number == chapter_number,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            # 更新
            existing.reading_power_score = score
            existing.hook_type = hook_type
            existing.hook_strength = hook_strength
            existing.hook_description = hook_description
            existing.coolpoint_patterns = coolpoint_patterns or []
            existing.micropayoffs = micropayoffs or []
            existing.is_transition = is_transition
            existing.transition_note = transition_note
            existing.evaluation_raw = evaluation_raw
            return existing

        rp = ChapterReadingPower(
            project_id=project_id,
            chapter_number=chapter_number,
            reading_power_score=score,
            hook_type=hook_type,
            hook_strength=hook_strength,
            hook_description=hook_description,
            coolpoint_patterns=coolpoint_patterns or [],
            micropayoffs=micropayoffs or [],
            is_transition=is_transition,
            transition_note=transition_note,
            evaluation_raw=evaluation_raw,
            debt_balance=Decimal("0.0"),
        )
        db.add(rp)
        await db.flush()
        return rp

    def _extract_chapter_text(self, chapter: Chapter) -> str:
        if isinstance(chapter.content, dict):
            return chapter.content.get("text", json.dumps(chapter.content, ensure_ascii=False))
        if isinstance(chapter.content, str):
            return chapter.content
        return str(chapter.content or "")

    async def _get_active_debt_total(self, db: AsyncSession, project_id: str) -> Decimal:
        result = await db.execute(
            select(func.coalesce(func.sum(ChaseDebt.current_amount), 0)).where(
                ChaseDebt.project_id == project_id,
                ChaseDebt.status.in_([DebtStatus.ACTIVE.value, DebtStatus.PARTIAL.value]),
            )
        )
        return Decimal(str(result.scalar() or 0))

    # ── 序列化辅助 ─────────────────────────────────────────────────────

    def _debt_to_dict(self, d: ChaseDebt) -> dict:
        return {
            "id": str(d.id),
            "project_id": str(d.project_id),
            "debt_type": d.debt_type,
            "description": d.description,
            "original_amount": float(d.original_amount),
            "current_amount": float(d.current_amount),
            "interest_rate": float(d.interest_rate),
            "source_chapter": d.source_chapter,
            "due_chapter": d.due_chapter,
            "paid_chapter": d.paid_chapter,
            "status": d.status,
            "contract_id": str(d.contract_id) if d.contract_id else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }

    def _debt_event_to_dict(self, e: DebtEvent) -> dict:
        return {
            "id": str(e.id),
            "debt_id": str(e.debt_id),
            "project_id": str(e.project_id),
            "event_type": e.event_type,
            "chapter_number": e.chapter_number,
            "amount_before": float(e.amount_before) if e.amount_before else None,
            "amount_after": float(e.amount_after) if e.amount_after else None,
            "amount_change": float(e.amount_change) if e.amount_change else None,
            "description": e.description,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }

    def _contract_to_dict(self, c: OverrideContract) -> dict:
        return {
            "id": str(c.id),
            "project_id": str(c.project_id),
            "chapter_number": c.chapter_number,
            "constraint_type": c.constraint_type,
            "rationale_type": c.rationale_type,
            "rationale_text": c.rationale_text,
            "payback_plan": c.payback_plan,
            "due_chapter": c.due_chapter,
            "fulfilled_chapter": c.fulfilled_chapter,
            "status": c.status,
            "auto_extend": c.auto_extend,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }