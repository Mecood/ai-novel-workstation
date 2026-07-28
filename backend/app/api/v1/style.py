"""Style Adapter 深度版 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.services.genre_weighted_style import GenreStyleWeighter, StyleVariantGenerator

router = APIRouter(prefix="/projects/{project_id}/style")


@router.get("/params")
async def get_style_params(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    genre: str = Query(None, description="题材名（不传则使用项目题材）"),
):
    """返回题材风格参数。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    genre_key = genre or project.genre or "都市日常"
    weighter = GenreStyleWeighter()
    params = weighter.get_style_params(genre_key)
    section = weighter.build_style_prompt_section(genre_key)

    return {
        "genre": genre_key,
        "resolved_genre": weighter._resolve_genre(genre_key),
        "params": params,
        "style_prompt_section": section,
    }


@router.get("/variants/options")
async def get_variant_options(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    genre: str = Query(None, description="题材名（不传则使用项目题材）"),
):
    """返回可用的风格变体选项。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    genre_key = genre or project.genre or "都市日常"
    generator = StyleVariantGenerator(db, project_id)
    return generator.get_variant_options(genre_key)


@router.post("/variants")
async def generate_style_variants(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    chapter_id: str | None = Query(None, description="章节ID（自动提取正文）"),
    text: str | None = Query(None, description="直接传入正文文本"),
    genre: str | None = Query(None, description="题材（不传则用项目）"),
    variant_ids: list[str] | None = Query(
        None,
        description="变体ID列表（如 serious/light/poetic/action/psychology）",
    ),
):
    """生成风格变体。返回每个变体的改写 prompt（由调用方发给 AI）。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # 取正文
    if text:
        base_text = text
    elif chapter_id:
        from app.models.chapter import Chapter
        chapter = await db.get(Chapter, chapter_id)
        if not chapter:
            raise HTTPException(404, "Chapter not found")
        import json
        content = chapter.content or {}
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except Exception:
                pass
        base_text = content.get("text", "") if isinstance(content, dict) else ""
    else:
        raise HTTPException(400, "需提供 text 或 chapter_id")

    genre_key = genre or project.genre or "都市日常"
    variant_ids = variant_ids or ["serious", "light", "poetic"]
    generator = StyleVariantGenerator(db, project_id)

    # 返回每个变体的改写 prompt
    variants = {}
    for vid in variant_ids:
        prompt_text = generator.generate_variant_prompt(base_text, str(genre_key), vid)
        variants[vid] = {
            "label": next(
                (v["label"] for v in [
                    {"id": "serious", "label": "严肃正剧"},
                    {"id": "light", "label": "轻松幽默"},
                    {"id": "poetic", "label": "诗意文学"},
                    {"id": "action", "label": "快节奏动作"},
                    {"id": "psychology", "label": "心理描写"},
                ] if v["id"] == vid), vid),
            "prompt": prompt_text,
        }

    return {
            "genre": genre_key,
            "variant_count": len(variants),
            "variants": variants,
        }


    @router.post("/apply")
    async def apply_style(
        project_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        prompt: str = Query(""),
    ):
        """将风格 prompt 应用到项目（写入 context.style_prompt）"""
        project = await db.get(Project, project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        if not prompt.strip():
            raise HTTPException(400, "必须提供 style prompt")
        ctx = dict(project.context or {})
        ctx["style_prompt"] = prompt
        project.context = ctx
        await db.commit()
        return {
            "status": "applied",
            "project_id": project_id,
            "style_prompt": prompt,
        }