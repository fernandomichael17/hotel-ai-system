from sqlalchemy.ext.asyncio import AsyncSession
from backend.rag.retriever import RAGRetriever
from typing import Optional

class FAQRetriever:
    """FAQ retriever — wrapper dari RAGRetriever khusus untuk FAQ workflow."""
    
    def __init__(self, db: AsyncSession):
        self.retriever = RAGRetriever(db)
    
    async def get_context(
        self,
        question: str,
        hotel_id: str,
        top_k: int = 4
    ) -> Optional[str]:
        """
        Ambil context untuk menjawab pertanyaan FAQ.
        
        Return None kalau tidak ada dokumen relevan ditemukan.
        Return string context kalau ada.
        """
        context = await self.retriever.retrieve_as_context(
            query=question,
            hotel_id=hotel_id,
            top_k=top_k
        )
        
        return context if context else None
