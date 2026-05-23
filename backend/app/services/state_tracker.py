"""Track story state: generated content, character appearances, foreshadowing status."""
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class StoryState:
    """Current state of story generation."""
    project_id: str
    generated_chapters: list[dict] = field(default_factory=list)
    character_appearances: dict[str, list[int]] = field(default_factory=dict)
    pending_foreshadowings: list[dict] = field(default_factory=list)
    last_checkpoint: Optional[dict] = None


class StateTracker:
    """Tracks story generation state across sessions."""
    
    def __init__(self):
        self._states: dict[str, StoryState] = {}
    
    def get_or_create(self, project_id: str) -> StoryState:
        if project_id not in self._states:
            self._states[project_id] = StoryState(project_id=project_id)
        return self._states[project_id]
    
    def record_chapter(self, project_id: str, chapter: dict):
        state = self.get_or_create(project_id)
        state.generated_chapters.append(chapter)
        state.last_checkpoint = {"type": "chapter", "data": chapter}
    
    def record_character_appearance(self, project_id: str, character_name: str, chapter_number: int):
        state = self.get_or_create(project_id)
        if character_name not in state.character_appearances:
            state.character_appearances[character_name] = []
        state.character_appearances[character_name].append(chapter_number)
    
    def get_unseen_characters(self, project_id: str, up_to_chapter: int) -> list[str]:
        state = self.get_or_create(project_id)
        unseen = []
        for name, chapters in state.character_appearances.items():
            if not any(c <= up_to_chapter for c in chapters):
                unseen.append(name)
        return unseen
    
    def record_foreshadowing(self, project_id: str, foreshadowing: dict):
        state = self.get_or_create(project_id)
        state.pending_foreshadowings.append(foreshadowing)
    
    def get_pending_foreshadowings(self, project_id: str) -> list[dict]:
        state = self.get_or_create(project_id)
        return [f for f in state.pending_foreshadowings if f.get("status") == "planted"]
    
    def mark_foreshadowing_paid_off(self, project_id: str, foreshadowing_id: str):
        state = self.get_or_create(project_id)
        for f in state.pending_foreshadowings:
            if f.get("id") == foreshadowing_id:
                f["status"] = "paid_off"
                break
    
    def to_dict(self, project_id: str) -> dict:
        state = self.get_or_create(project_id)
        return {
            "project_id": state.project_id,
            "chapter_count": len(state.generated_chapters),
            "character_appearances": state.character_appearances,
            "pending_foreshadowings": len(self.get_pending_foreshadowings(project_id)),
            "last_checkpoint": state.last_checkpoint,
        }