"""SkillRegistry — singleton service that scans and indexes skill files.

Skills are defined as SKILL.md files in backend/app/skills/.
Each file has YAML frontmatter with metadata and Markdown body with instructions.
The registry scans the directory at startup and indexes skills by task name.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Determine the skills directory relative to this file.
# Structure: backend/app/services/skill_registry.py → backend/app/skills/
_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass
class SkillDefinition:
    """A parsed skill definition from a SKILL.md file."""
    name: str
    category: str
    description: str
    version: str
    tasks: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    priority: int = 5
    content: str = ""       # SKILL.md body (without YAML frontmatter)
    file_path: str = ""


class SkillRegistry:
    """Singleton that scans the skills/ directory and indexes by task name.

    Usage:
        registry = SkillRegistry.get_instance()
        registry.scan_directory()
        skills = registry.get_skills_for_task("generate_chapter")
    """

    _instance: Optional["SkillRegistry"] = None
    _skills: dict[str, SkillDefinition] = {}   # name → SkillDefinition
    _by_task: dict[str, list[str]] = {}         # task → [skill_name, ...]
    _scanned: bool = False

    def __init__(self) -> None:
        if SkillRegistry._instance is not None:
            raise RuntimeError("Use SkillRegistry.get_instance() — singleton.")
        SkillRegistry._instance = self

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        """Return the singleton instance, creating it if necessary."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan_directory(self, base_path: Optional[str] = None) -> None:
        """Scan the skills directory recursively for SKILL.md files.

        Args:
            base_path: Optional override for the skills directory.
                       Defaults to the ``skills/`` sibling of this package.
        """
        root = Path(base_path) if base_path else _SKILLS_DIR
        if not root.exists():
            logger.warning(
                "Skills directory not found at %s — skipping scan.",
                root,
            )
            return

        count = 0
        for skill_file in root.rglob("SKILL.md"):
            try:
                definition = self._parse_skill_file(skill_file)
                if definition:
                    self._skills[definition.name] = definition
                    for task in definition.tasks:
                        task_key = task.strip().lower()
                        if task_key:
                            self._by_task.setdefault(task_key, []).append(
                                definition.name
                            )
                    count += 1
            except Exception:
                logger.exception(
                    "Failed to parse skill file %s — skipping.", skill_file
                )

        self._scanned = True
        logger.info(
            "SkillRegistry scanned %d skill(s) from %s indexed %d task(s).",
            count,
            root,
            len(self._by_task),
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_skill_file(file_path: Path) -> Optional[SkillDefinition]:
        """Parse a single SKILL.md file into a SkillDefinition.

        Expects YAML frontmatter delimited by ``---`` followed by Markdown body.
        """
        raw = file_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        if len(parts) < 3:
            logger.warning("%s has no YAML frontmatter.", file_path)
            return None

        frontmatter_text = parts[1].strip()
        body = parts[2].strip()

        try:
            meta: dict = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError:
            logger.exception("Bad YAML frontmatter in %s.", file_path)
            return None

        name = meta.get("name", "").strip()
        if not name:
            logger.warning("%s has no 'name' in frontmatter.", file_path)
            return None

        return SkillDefinition(
            name=name,
            category=str(meta.get("category", "general")).strip(),
            description=str(meta.get("description", "")).strip(),
            version=str(meta.get("version", "1.0.0")).strip(),
            tasks=[t.strip() for t in meta.get("tasks", []) if isinstance(t, str)],
            triggers=[t.strip() for t in meta.get("triggers", []) if isinstance(t, str)],
            priority=int(meta.get("priority", 5)),
            content=body,
            file_path=str(file_path),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_skills_for_task(self, task: str) -> list[SkillDefinition]:
        """Return skills that match the given task name (case-insensitive).

        Args:
            task: The task identifier, e.g. ``"generate_chapter"``.

        Returns:
            List of matching SkillDefinitions, sorted by priority descending.
        """
        if not self._scanned:
            logger.warning("SkillRegistry has not been scanned yet.")
            return []

        task_key = task.strip().lower()
        names = self._by_task.get(task_key, [])
        result = [self._skills[n] for n in names if n in self._skills]
        result.sort(key=lambda s: s.priority, reverse=True)
        return result

    def list_all(self) -> list[SkillDefinition]:
        """Return all registered skills, sorted by (category, name)."""
        if not self._scanned:
            logger.warning("SkillRegistry has not been scanned yet.")
            return []

        return sorted(
            self._skills.values(),
            key=lambda s: (s.category, s.name),
        )

    def get_by_name(self, name: str) -> Optional[SkillDefinition]:
        """Look up a single skill by name."""
        if not self._scanned:
            return None
        return self._skills.get(name.strip())

    # ------------------------------------------------------------------
    # Prompt injection helper
    # ------------------------------------------------------------------

    def build_skill_context(
        self,
        task: str,
        enabled_names: Optional[set[str]] = None,
        max_chars: int = 2000,
    ) -> str:
        """Build a prompt injection snippet for the given task.

        Args:
            task: The task to match skills for.
            enabled_names: If provided, only include skills in this set.
            max_chars: Truncate each skill's body content to this many chars.

        Returns:
            A string ready to inject into a system prompt, or an empty string
            if no matching skills were found.
        """
        skills = self.get_skills_for_task(task)
        if not skills:
            return ""

        if enabled_names is not None:
            skills = [s for s in skills if s.name in enabled_names]

        if not skills:
            return ""

        parts: list[str] = []
        for s in skills:
            body = s.content[:max_chars]
            parts.append(f"## Skill: {s.name}\n{body}")

        return "\n\n".join(parts)


# ------------------------------------------------------------------
# Convenience alias for lazy loading
# ------------------------------------------------------------------
def get_registry() -> SkillRegistry:
    """Return the singleton SkillRegistry, scanning on first call.

    This is the recommended way to obtain the registry from application code.
    It is safe to call multiple times — scanning happens at most once.
    """
    instance = SkillRegistry.get_instance()
    if not instance._scanned:
        instance.scan_directory()
    return instance