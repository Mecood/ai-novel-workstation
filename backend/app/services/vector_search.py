"""Vector search service using ChromaDB for story context retrieval.
Supports semantic search + Reranker for better relevance ranking.
"""
import hashlib
from typing import Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings

from app.core.ai_client import AIClient


class VectorSearchService:
    """Service for semantic search over story content with reranking."""

    # 硅基流动支持的 reranker 模型
    RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
    RERANKER_BASE_URL = "https://api.siliconflow.cn/v1"

    def __init__(self, persist_dir: str = "./storage/vectorstore", siliconflow_api_key: str = ""):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._siliconflow_api_key = siliconflow_api_key
        self._reranker_client: Optional[AIClient] = None

    def _get_reranker_client(self) -> AIClient:
        """Get or create reranker client."""
        if self._reranker_client is None:
            self._reranker_client = AIClient(
                url=self.RERANKER_BASE_URL,
                api_key=self._siliconflow_api_key,
                model=self.RERANKER_MODEL,
            )
        return self._reranker_client

    async def close(self):
        """Close all clients."""
        if self._reranker_client:
            await self._reranker_client.close()

    def _get_collection(self, project_id: str):
        """Get or create a collection for a project."""
        collection_name = f"project_{project_id.replace('-', '_')[:63]}"
        try:
            return self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            return self.client.get_collection(collection_name)

    def _chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
        """Split text into overlapping chunks at sentence boundaries."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break
            # Try to break at a sentence boundary
            search_start = max(start, end - overlap)
            for sep in ["。", "！", "？", "\n", ".", "!", "?"]:
                break_at = text.rfind(sep, search_start, end)
                if break_at != -1:
                    chunks.append(text[start:break_at + 1])
                    start = break_at + 1
                    break
            else:
                chunks.append(text[start:end])
                start = end - overlap

        return chunks

    async def add_content(self, project_id: str, content: str, metadata: dict, ai_client: AIClient):
        """Add content to vector store with embeddings."""
        collection = self._get_collection(project_id)
        chunks = self._chunk_text(content)

        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{metadata.get('chapter', 0)}_{i}_{len(chunks)}".encode()).hexdigest()
            embedding = await ai_client.embed(chunk)

            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{**metadata, "chunk_index": i}],
            )

    async def search(
        self, project_id: str, query: str, top_k: int = 5, ai_client: Optional[AIClient] = None
    ) -> list[dict]:
        """Search for most relevant content chunks with optional reranking."""
        collection = self._get_collection(project_id)
        query_embedding = await ai_client.embed(query)

        # ChromaDB 返回的原始结果（可能比 top_k 多一些用于 rerank）
        search_k = min(top_k * 3, collection.count())
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=search_k,
        )

        if not results["ids"]:
            return []

        documents = []
        for i in range(len(results["ids"][0])):
            documents.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })

        return documents

    async def search_with_rerank(
        self, project_id: str, query: str, top_k: int = 5, ai_client: Optional[AIClient] = None
    ) -> list[dict]:
        """Search with reranking for better relevance."""
        # 先用向量检索召回候选
        candidates = await self.search(project_id, query, top_k=top_k * 3, ai_client=ai_client)

        if not candidates:
            return []

        # 用 reranker 对候选重新排序
        reranker = self._get_reranker_client()
        passages = [c["content"] for c in candidates]

        try:
            # 硅基流动 reranker API 格式
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.RERANKER_BASE_URL}/rerank",
                    json={
                        "model": self.RERANKER_MODEL,
                        "query": query,
                        "documents": passages,
                        "top_n": top_k,
                    },
                    headers={"Authorization": f"Bearer {self._siliconflow_api_key}"},
                )
                resp.raise_for_status()
                rerank_data = resp.json()

                # 按 rerank 分数排序
                results = []
                for r in rerank_data.get("results", []):
                    idx = r["index"]
                    if idx < len(candidates):
                        c = candidates[idx]
                        c["rerank_score"] = r.get("relevance_score", 0)
                        results.append(c)

                return results

        except Exception as e:
            # Rerank 失败时返回原始向量检索结果
            return candidates[:top_k]

    async def get_context_for_chapter(
        self, project_id: str, chapter_topic: str, max_chunks: int = 5,
        use_rerank: bool = True, ai_client: Optional[AIClient] = None
    ) -> str:
        """Get relevant context for generating a new chapter."""
        if ai_client is None:
            raise ValueError("ai_client is required for vector search")

        if use_rerank and self._siliconflow_api_key:
            results = await self.search_with_rerank(
                project_id, chapter_topic, top_k=max_chunks, ai_client=ai_client
            )
        else:
            results = await self.search(
                project_id, chapter_topic, top_k=max_chunks, ai_client=ai_client
            )

        if not results:
            return ""

        context_parts = []
        for r in results:
            meta = r["metadata"]
            chapter_num = meta.get("chapter", "?")
            score_info = ""
            if "rerank_score" in r:
                score_info = f" (relevance: {r['rerank_score']:.3f})"
            elif "distance" in r and r["distance"] is not None:
                score_info = f" (distance: {r['distance']:.3f})"
            context_parts.append(f"[第{chapter_num}章相关片段{score_info}]\n{r['content']}")

        return "\n\n".join(context_parts)

    async def get_all_chunks(self, project_id: str) -> list[dict]:
        """Get all chunks for a project (for consistency check)."""
        collection = self._get_collection(project_id)
        count = collection.count()
        if count == 0:
            return []

        results = collection.get(include=["documents", "metadatas"])
        chunks = []
        for i in range(len(results["ids"])):
            chunks.append({
                "id": results["ids"][i],
                "content": results["documents"][i],
                "metadata": results["metadatas"][i],
            })
        return chunks
