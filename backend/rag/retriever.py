from typing import List, Dict, Any
import uuid
from sqlalchemy import select
from ..db.database import AsyncSessionLocal
from ..db.models import Document
from ..integrations.llm.embedder import TextEmbedder

class RAGRetriever:
    """Retriever for RAG workflow."""
    
    def __init__(self, embedder: TextEmbedder):
        self.embedder = embedder
        
    async def retrieve(self, query: str, hotel_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve top k relevant documents for query."""
        query_vec = await self.embedder.embed(query)
        
        async with AsyncSessionLocal() as db_session:
            stmt = (
                select(Document)
                .where(Document.hotel_id == uuid.UUID(hotel_id))
                .order_by(Document.embedding.cosine_distance(query_vec))
                .limit(top_k)
            )
            
            result = await db_session.execute(stmt)
            docs = result.scalars().all()
            
            return [
                {
                    "content": doc.content,
                    "title": doc.title,
                    "score": 0.0  # Optional: calculate actual similarity score if needed
                }
                for doc in docs
            ]
