"""
伏笔 DAG 服务 — 依赖关系图 + 自动到期检查。

功能：
- check_expired_foreshadowings: 检查是否有伏笔到期未回收，自动标记 abandoned
- get_foreshadowing_dag: 返回伏笔 DAG 结构（nodes + edges）
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foreshadowing import Foreshadowing


async def check_expired_foreshadowings(
    db: AsyncSession,
    project_id: str,
    current_chapter: int,
) -> list[dict]:
    """
    检查是否有伏笔到期未回收，自动标记 abandoned。

    规则：
    - expected_redemption_chapter 非空且 <= current_chapter
    - status 为 'planted' 或 'active'
    - auto_check_enabled = True
    """
    result = await db.execute(
        select(Foreshadowing).where(
            Foreshadowing.project_id == project_id,
            Foreshadowing.expected_redemption_chapter.isnot(None),
            Foreshadowing.expected_redemption_chapter <= current_chapter,
            Foreshadowing.status.in_(["planted", "active"]),
            Foreshadowing.auto_check_enabled == True,  # noqa: E712
        )
    )
    expired = result.scalars().all()

    marked = []
    for f in expired:
        f.status = "abandoned"
        marked.append({
            "id": str(f.id),
            "title": f.title,
            "expected_chapter": f.expected_redemption_chapter,
            "current_chapter": current_chapter,
        })

    if marked:
        await db.commit()

    return marked


async def get_foreshadowing_dag(
    db: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    """
    返回伏笔 DAG 结构：nodes + edges。

    Nodes:
    - id: 伏笔 ID
    - title: 标题
    - status: planted / active / paid_off / abandoned
    - target_chapter: 目标章节
    - expected_redemption_chapter: 到期章节
    - dependency_type: prerequisite / parallel / chain

    Edges:
    - source: 依赖方 ID
    - target: 被依赖方 ID
    - type: 依赖类型
    """
    result = await db.execute(
        select(Foreshadowing).where(Foreshadowing.project_id == project_id)
    )
    foreshadowings = result.scalars().all()

    nodes = []
    edges = []
    id_map = {str(f.id): f for f in foreshadowings}

    for f in foreshadowings:
        fid = str(f.id)
        nodes.append({
            "id": fid,
            "title": f.title or "未命名伏笔",
            "status": f.status or "planted",
            "target_chapter": f.target_chapter,
            "expected_redemption_chapter": f.expected_redemption_chapter,
            "dependency_type": f.dependency_type or "prerequisite",
            "description": (f.description or "")[:100],
        })

        # 解析 depends_on 构建边
        deps = f.depends_on or []
        for dep_id in deps:
            dep_str = str(dep_id)
            if dep_str in id_map:
                edges.append({
                    "source": fid,
                    "target": dep_str,
                    "type": f.dependency_type or "prerequisite",
                    "label": f.dependency_type or "前置",
                })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }