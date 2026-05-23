from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
import io
import zipfile
from datetime import date

from app.core.database import get_db
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.character import Character
from app.models.chapter import Chapter
from app.models.foreshadowing import Foreshadowing
from app.models.knowledge import Knowledge
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    count_query = select(func.count(Project.id))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = select(Project).offset(skip).limit(limit).order_by(Project.created_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()

    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
    )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        name=data.name,
        description=data.description,
        genre=data.genre,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()


@router.get("/{project_id}/export")
async def export_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    # 查项目
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 查所有关联数据
    wv_r = await db.execute(select(Worldview).where(Worldview.project_id == project_id))
    worldviews = wv_r.scalars().all()

    ch_r = await db.execute(select(Character).where(Character.project_id == project_id))
    characters = ch_r.scalars().all()

    cp_r = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
    )
    chapters = cp_r.scalars().all()

    fs_r = await db.execute(select(Foreshadowing).where(Foreshadowing.project_id == project_id))
    foreshadowings = fs_r.scalars().all()

    kn_r = await db.execute(select(Knowledge).where(Knowledge.project_id == project_id))
    knowledges = kn_r.scalars().all()

    safe_name = project.name.replace("/", "_").replace("\\", "_")
    base = safe_name

    def json_to_text(val):
        if val is None:
            return "无"
        if isinstance(val, dict):
            return "\n".join(f"- **{k}**: {v}" for k, v in val.items())
        if isinstance(val, list):
            return "\n".join(f"- {v}" for v in val)
        return str(val)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 项目信息
        info = f"""# {project.name}

**题材**: {project.genre or "未设置"}
**状态**: {project.status}
**描述**: {project.description or "无"}
**创建时间**: {project.created_at}

"""
        if project.story_core:
            info += "## 故事核心\n\n"
            if isinstance(project.story_core, dict):
                for k, v in project.story_core.items():
                    info += f"- **{k}**: {v}\n"
        zf.writestr(f"{base}/项目信息.md", info)

        # 世界观
        for wv in worldviews:
            content = f"""# {wv.name}

{wv.description}

"""
            if wv.rules:
                content += "## 规则\n\n" + json_to_text(wv.rules) + "\n\n"
            if wv.timeline:
                content += "## 时间线\n\n" + json_to_text(wv.timeline)
            zf.writestr(f"{base}/世界观/{wv.name}.md", content)

        # 角色
        for ch in characters:
            content = f"""# {ch.name}

**角色定位**: {ch.role_type}

"""
            if ch.appearance:
                content += f"## 外貌\n\n{ch.appearance}\n\n"
            if ch.background:
                content += f"## 背景\n\n{ch.background}\n\n"
            if ch.personality:
                content += "## 性格\n\n" + json_to_text(ch.personality) + "\n\n"
            if ch.relationships:
                content += "## 关系\n\n" + json_to_text(ch.relationships) + "\n\n"
            if ch.arc:
                content += "## 成长弧线\n\n" + json_to_text(ch.arc)
            zf.writestr(f"{base}/角色/{ch.name}.md", content)

        # 章节
        for cp in chapters:
            text_content = ""
            if cp.content:
                if isinstance(cp.content, dict):
                    text_content = cp.content.get("text", cp.content.get("content", str(cp.content)))
                elif isinstance(cp.content, str):
                    text_content = cp.content
                else:
                    text_content = str(cp.content)
            content = f"""# 第{cp.chapter_number}章 {cp.title}

"""
            if cp.summary:
                content += f"> 摘要：{cp.summary}\n\n"
            content += text_content
            zf.writestr(f"{base}/章节/第{cp.chapter_number:03d}章_{cp.title}.md", content)

        # 伏笔
        fsh_text = "# 伏笔追踪\n\n"
        status_emoji_map = {"planted": "🟢 已埋设", "progress": "🟡 推进中", "resolved": "🔵 已回收"}
        for fs in foreshadowings:
            emoji = status_emoji_map.get(fs.status, fs.status)
            fsh_text += f"""### {fs.title}
- **描述**: {fs.description}
- **目标章节**: {fs.target_chapter or "未指定"}
- **状态**: {emoji}

"""
        zf.writestr(f"{base}/伏笔追踪.md", fsh_text)

        # 知识库
        for kn in knowledges:
            category = kn.category or "未分类"
            tags_str = ", ".join(kn.tags) if kn.tags else "无"
            content = f"""# {kn.title}

**分类**: {category}
**标签**: {tags_str}

{kn.content or "无内容"}
"""
            zf.writestr(f"{base}/知识库/{category}/{kn.title}.md", content)

    buf.seek(0)
    filename = f"{safe_name}_export_{date.today().isoformat()}.zip"
    import urllib.parse
    encoded_filename = urllib.parse.quote(filename)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )