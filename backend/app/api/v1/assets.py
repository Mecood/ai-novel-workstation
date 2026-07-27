"""Assets API — project asset management (scene images, etc.)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.project_asset import ProjectAsset
from app.services.image_service import ImageService

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])
image_service = ImageService()


class GenerateSceneRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="场景描述文本")
    label: str = Field(default="", max_length=255, description="场景图标签")


class AssetResponse(BaseModel):
    id: str
    project_id: str
    type: str
    label: str | None
    url: str
    prompt: str | None
    created_at: str

    class Config:
        from_attributes = True


class ListAssetsResponse(BaseModel):
    items: list[AssetResponse]


@router.post("/generate-scene", response_model=AssetResponse)
async def generate_scene_image(
    project_id: UUID,
    body: GenerateSceneRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a scene image for a project via AI image generation API.

    Saves the generated image locally under `storage/images/` and records
    metadata in the `project_assets` table. Returns the asset record with
    the relative URL path.
    """
    # Verify project exists
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Call the image generation service
    try:
        result = await image_service.generate_image(
            db=db,
            prompt=body.prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图像生成异常: {e}")

    # Create asset record
    asset = ProjectAsset(
        project_id=project_id,
        type="scene_image",
        label=body.label or "",
        url=result["url"],
        prompt=body.prompt,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return AssetResponse(
        id=str(asset.id),
        project_id=str(asset.project_id),
        type=asset.type,
        label=asset.label,
        url=asset.url,
        prompt=asset.prompt,
        created_at=asset.created_at.isoformat() if asset.created_at else None,
    )


@router.get("", response_model=ListAssetsResponse)
async def list_assets(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all assets for a project, newest first."""
    result = await db.execute(
        select(ProjectAsset)
        .where(ProjectAsset.project_id == project_id)
        .order_by(ProjectAsset.created_at.desc())
    )
    assets = result.scalars().all()
    return ListAssetsResponse(
        items=[
            AssetResponse(
                id=str(a.id),
                project_id=str(a.project_id),
                type=a.type,
                label=a.label,
                url=a.url,
                prompt=a.prompt,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
            for a in assets
        ]
    )