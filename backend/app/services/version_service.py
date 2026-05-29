"""Version management service for content nodes."""
import json
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.worldview import Worldview
from app.models.character import Character
from app.models.chapter import Chapter
from app.models.volume import Volume
from app.models.project import Project


class VersionService:
    """Manage versioning, history, and cascade staleness for content nodes."""

    # ── Story Core (stored inside Project.story_core JSON) ──

    @staticmethod
    def get_story_core_version(project: Project) -> int:
        if not project.story_core:
            return 0
        return int(project.story_core.get("_version", 0) or 0)

    @staticmethod
    def save_story_core_snapshot(project: Project):
        """Save current story_core to history, bump version."""
        sc = project.story_core or {}
        version = int(sc.get("_version", 0) or 0)
        history = sc.get("_history", [])

        # Save snapshot of current state (without internal fields)
        snapshot = {
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": {k: v for k, v in sc.items() if not k.startswith("_")},
        }
        history.append(snapshot)

        # Bump version
        sc["_version"] = version + 1
        sc["_history"] = history
        project.story_core = sc

    @staticmethod
    def restore_story_core_version(project: Project, target_version: int) -> bool:
        """Restore story_core to a specific version. Returns True if successful."""
        sc = project.story_core or {}
        history = sc.get("_history", [])

        # Find target snapshot
        target = None
        for h in history:
            if h.get("version") == target_version:
                target = h
                break

        if not target:
            return False

        # Save current state as new snapshot
        current_snapshot = {
            "version": int(sc.get("_version", 0) or 0),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": {k: v for k, v in sc.items() if not k.startswith("_")},
        }
        history.append(current_snapshot)

        # Restore
        restored = target["data"].copy()
        restored["_version"] = target_version
        restored["_history"] = history
        project.story_core = restored
        return True

    # ── Generic node operations ──

    @staticmethod
    def snapshot_node(node) -> dict:
        """Extract node data as a dict for history storage."""
        data = {}
        # Get all non-internal columns
        for col in node.__table__.columns:
            name = col.name
            if name.startswith("_"):
                continue
            if name in ("id", "project_id", "created_at", "updated_at"):
                continue
            val = getattr(node, name)
            if val is not None:
                # Serialize JSON fields
                if isinstance(val, (list, dict)):
                    data[name] = val
                else:
                    data[name] = val
        return data

    @staticmethod
    async def save_and_bump(
        db: AsyncSession,
        node,
        based_on: dict,
    ):
        """Save current node data to history, bump version, set based_on."""
        current_version = node._version or 0
        current_data = VersionService.snapshot_node(node)

        history = node._history or []
        history.append({
            "version": current_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "based_on": node._based_on or {},
            "data": current_data,
        })

        node._version = current_version + 1
        node._based_on = based_on
        node._history = history
        node._stale = "false"
        await db.flush()

    @staticmethod
    async def mark_downstream_stale(
        db: AsyncSession,
        project_id: str,
        source_name: str,
    ):
        """Mark downstream nodes as stale when source changes.

        source_name: "story_core" / "worldview" / "characters"
        """
        stale_targets = []

        if source_name == "story_core":
            # Everything downstream
            stale_targets = ["worldview", "characters", "volumes", "chapters"]
        elif source_name == "worldview":
            stale_targets = ["volumes", "chapters"]
        elif source_name == "characters":
            stale_targets = ["volumes", "chapters"]

        if "worldview" in stale_targets:
            await db.execute(
                update(Worldview)
                .where(Worldview.project_id == project_id)
                .values(_stale="true")
            )
        if "characters" in stale_targets:
            await db.execute(
                update(Character)
                .where(Character.project_id == project_id)
                .values(_stale="true")
            )
        if "volumes" in stale_targets:
            await db.execute(
                update(Volume)
                .where(Volume.project_id == project_id)
                .values(_stale="true")
            )
        if "chapters" in stale_targets:
            await db.execute(
                update(Chapter)
                .where(Chapter.project_id == project_id)
                .values(_stale="true")
            )

        await db.flush()

    @staticmethod
    async def restore_node_version(db: AsyncSession, node, target_version: int) -> bool:
        """Restore a node (worldview/character/chapter/volume) to a specific version."""
        history = node._history or []

        target = None
        for h in history:
            if h.get("version") == target_version:
                target = h
                break
        if not target:
            return False

        # Save current state as snapshot
        current_data = VersionService.snapshot_node(node)
        current_snapshot = {
            "version": node._version or 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "based_on": node._based_on or {},
            "data": current_data,
        }
        history.append(current_snapshot)

        # Restore data
        for key, val in target["data"].items():
            if hasattr(node, key):
                setattr(node, key, val)

        node._version = target_version
        node._based_on = target.get("based_on", {})
        node._history = history
        node._stale = "false"
        await db.flush()
        return True

    # ── Upstream versions ──

    @staticmethod
    async def get_upstream_versions(db: AsyncSession, project_id: str) -> dict:
        """Get current versions of all upstream nodes."""
        versions = {}

        # Story core from Project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project and project.story_core:
            versions["story_core"] = int(project.story_core.get("_version", 0) or 0)

        # Worldview
        result = await db.execute(
            select(Worldview._version).where(Worldview.project_id == project_id)
        )
        row = result.scalar_one_or_none()
        versions["worldview"] = row or 0

        # Characters (aggregate: max version across all characters)
        result = await db.execute(
            select(Character._version).where(Character.project_id == project_id)
        )
        rows = result.scalars().all()
        versions["characters"] = max(rows) if rows else 0

        return versions


version_service = VersionService()
