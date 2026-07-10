from sqlalchemy.ext.asyncio import AsyncSession
from backend.integrations.llm.embedder import embedder
from backend.db.repositories.document_repo import DocumentRepository

class RAGRetriever:
    """Retriever untuk mencari dan mencocokkan dokumen relevan berbasis kueri embedding."""
    
    def __init__(self, db: AsyncSession):
        self.repo = DocumentRepository(db)
        
    async def retrieve(
        self,
        query: str,
        hotel_id: str,
        top_k: int = 5,
        min_score: float = 0.42
    ) -> list[dict]:
        """Melakukan pencarian dokumen paling relevan menggunakan pgvector cosine distance."""
        # Pra-pembersihan sapaan & basa-basi agar pencarian semantik lebih fokus pada kata kunci inti
        import re
        clean_query = query.lower().strip()
        clean_query = re.sub(r"^(halo|hi|helo|permisi|tanya|mau tanya|tolong|tanya dong|saya mau tanya|saya ingin tanya|misi)\s+", "", clean_query)
        clean_query = clean_query.strip()
        
        query_embedding = embedder.embed(clean_query)
        
        results = await self.repo.similarity_search(
            query_embedding=query_embedding,
            hotel_id=hotel_id,
            top_k=top_k,
            min_score=min_score
        )
        return results
        
    async def retrieve_as_context(
        self,
        query: str,
        hotel_id: str,
        top_k: int = 5
    ) -> str:
        """Mengambil data kemiripan lalu memformatnya dalam bentuk list string terstruktur untuk prompt LLM."""
        results = await self.retrieve(
            query=query,
            hotel_id=hotel_id,
            top_k=top_k
        )
        
        if not results:
            return ""
            
        context_parts = []
        for r in results:
            context_parts.append(
                f"[Sumber: {r['title']}]\n{r['content']}"
            )
            
        return "\n\n".join(context_parts)
