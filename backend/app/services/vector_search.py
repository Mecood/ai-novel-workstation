"""Vector search service using ChromaDB for story context retrieval."""
import hashlib
from typing import Optional

import chromadb
from chromadb.config import Settings

from app.core.ai_client import AIClient


class VectorSearchService:
    """Service for semantic search over story content."""
    
    def __init__(self, persist_dir: str = "./storage/vectorstore"):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.ai_client = AIClient()
    
    def _get_collection(self, project_id: str):
        """Get or create a collection for a project."""
        collection_name = f"project_{project_id.replace('-', '_')[:63]}"
        try:
            return self.client.get_collection(collection_name)
        except ValueError:
            return self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
    
    def _chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
        """Split text into overlapping chunks."""
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
    
    async def add_content(self, project_id: str, content: str, metadata: dict):
        """Add content to vector store."""
        collection = self._get_collection(project_id)
        chunks = self._chunk_text(content)
        
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{metadata.get('chapter', 0)}_{i}".encode()).hexdigest()
            embedding = await self.ai_client.embed(chunk)
            
            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{**metadata, "chunk_index": i}],
            )
    
    async def search(
        self, project_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Search for most relevant content chunks."""
        collection = self._get_collection(project_id)
        query_embedding = await self.ai_client.embed(query)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
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
    
    async def get_context_for_chapter(
        self, project_id: str, chapter_topic: str, max_chunks: int = 5
    ) -> str:
        """Get relevant context for generating a new chapter."""
        results = await self.search(project_id, chapter_topic, top_k=max_chunks)
        if not results:
            return ""
        
        context_parts = []
        for r in results:
            meta = r["metadata"]
            chapter_num = meta.get("chapter", "?")
            context_parts.append(f"[第{chapter_num}章相关片段]\n{r['content']}")
        
        return "\n\n".join(context_parts)