"""Simple full-text search service using SQLite LIKE matching.

Replaces the old vector/embedding search (which depended on broken SiliconFlow API)
with pure text-based inverted-index-style search across chapters, characters,
worldview, and knowledge content.
"""

import sqlite3
import hashlib
import json
from typing import Optional
from pathlib import Path


class SimpleSearchService:
    """Pure text search over story content — no external AI / embeddings needed."""

    # Tables and their content columns for search
    TABLES = {
        "chapters": {
            "table": "chapters",
            "title_col": "title",
            "content_col": "content",
            "content_is_json": True,
            "json_path": "$.text",
            "type_label": "chapter",
        },
        "characters": {
            "table": "characters",
            "title_col": "name",
            "content_cols": ["name", "role_type", "personality", "background", "appearance"],
            "content_is_json": False,
            "type_label": "character",
        },
        "worldviews": {
            "table": "worldviews",
            "title_col": "name",
            "content_cols": ["name", "description"],
            "content_is_json": False,
            "type_label": "worldview",
        },
        "knowledges": {
            "table": "knowledges",
            "title_col": "title",
            "content_cols": ["title", "content", "source_type"],
            "content_is_json": False,
            "type_label": "knowledge",
        },
    }

    def __init__(self, db_path: str):
        """db_path: path to the SQLite database file."""
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _split_keywords(query: str) -> list[str]:
        """Split a query into meaningful keywords for LIKE matching."""
        # Remove punctuation, split on whitespace
        import re
        tokens = re.findall(r"[\u4e00-\u9fff\w]+", query)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in tokens:
            if t.lower() not in seen and len(t) >= 1:
                seen.add(t.lower())
                unique.append(t)
        return unique

    def search(
        self, project_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Full-text LIKE search across chapters, characters, worldview, knowledge.

        Returns a list of results with id, content, source (type_label), score,
        and metadata (title, etc.).
        """
        keywords = self._split_keywords(query)
        if not keywords:
            return []

        conn = self._connect()
        all_results = []

        for source, cfg in self.TABLES.items():
            try:
                where_clauses = []
                params: list[str] = [project_id]

                is_json = cfg.get("content_is_json", False)
                if is_json:
                    content_expr = f"json_extract({cfg['content_col']}, '{cfg['json_path']}')"
                else:
                    # Combine multiple content columns
                    cols = cfg.get("content_cols", [cfg["content_col"]])
                    content_expr = " || ' ' || ".join(
                        f"COALESCE({c}, '')" for c in cols
                    )

                # Build LIKE clauses for each keyword
                for kw in keywords:
                    pattern = f"%{kw}%"
                    where_clauses.append(f"({content_expr} LIKE ? OR {cfg['title_col']} LIKE ?)")
                    params.extend([pattern, pattern])

                where_sql = " AND ".join(where_clauses)
                sql = f"""
                    SELECT id, {cfg['title_col']} as title, {content_expr} as content
                    FROM {cfg['table']}
                    WHERE project_id = ? AND {where_sql}
                    LIMIT 10
                """
                cur = conn.execute(sql, params)

                for row in cur.fetchall():
                    row_dict = dict(row)
                    content = row_dict.get("content", "") or ""
                    title = row_dict.get("title", "") or ""

                    # Score: count keyword occurrences in content + title (simple relevance)
                    score = 0
                    for kw in keywords:
                        score += content.lower().count(kw.lower()) * 2
                        score += title.lower().count(kw.lower()) * 5

                    # Truncate long content for display
                    if len(content) > 600:
                        content = content[:600] + "..."

                    all_results.append({
                        "id": row_dict["id"],
                        "content": content,
                        "source": cfg["type_label"],
                        "score": score,
                        "metadata": {
                            "title": title,
                            "type": cfg["type_label"],
                        },
                    })

            except Exception as e:
                # Table doesn't exist or other transient error — skip
                continue

        # Sort by score descending, then take top_k
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    def get_context_for_chapter(
        self, project_id: str, topic: str, max_chunks: int = 5
    ) -> str:
        """Get relevant context for generating a new chapter — same keyword
        search but formatted as a context string."""
        results = self.search(project_id, topic, top_k=max_chunks)

        if not results:
            return ""

        context_parts = []
        for r in results:
            meta = r["metadata"]
            type_label = meta.get("type", "?")

            context_parts.append(
                f"[{type_label}: {meta.get('title', '?')} (score: {r['score']})]\n{r['content']}"
            )

        return "\n\n".join(context_parts)