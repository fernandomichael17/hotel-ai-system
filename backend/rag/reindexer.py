import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.integrations.llm.embedder import embedder
from backend.db.repositories.document_repo import DocumentRepository
from backend.db.models import Hotel

logger = logging.getLogger(__name__)

class DocumentReindexer:
    """Modul reindexer untuk meremajakan (re-embed) seluruh dokumen RAG."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DocumentRepository(db)
        
    async def reindex_hotel(
        self,
        hotel_id: str
    ) -> int:
        """Meng-embed ulang seluruh dokumen untuk satu hotel tertentu."""
        hotel_uuid = UUID(hotel_id)
        docs = await self.repo.find_by_hotel(hotel_uuid, active_only=False)
        if not docs:
            logger.info(f"Tidak ada dokumen yang ditemukan untuk hotel ID: {hotel_id}")
            return 0
            
        contents = [doc.content for doc in docs]
        embeddings = embedder.embed_batch(contents, is_passage=True)
        
        for doc, emb in zip(docs, embeddings):
            doc.embedding = emb
            
        await self.db.commit()
        return len(docs)
        
    async def reindex_all(self) -> dict:
        """Meng-embed ulang seluruh dokumen untuk semua hotel terdaftar."""
        result = await self.db.execute(select(Hotel))
        hotels = result.scalars().all()
        
        stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "hotels_processed": 0
        }
        
        for hotel in hotels:
            try:
                logger.info(f"Memulai re-index untuk hotel: {hotel.name} (ID: {hotel.id})")
                count = await self.reindex_hotel(str(hotel.id))
                stats["total"] += count
                stats["success"] += count
                stats["hotels_processed"] += 1
                logger.info(f"Berhasil mere-index {count} dokumen untuk hotel {hotel.name}.")
            except Exception as e:
                logger.error(f"Gagal mere-index hotel {hotel.name} (ID: {hotel.id}): {str(e)}")
                stats["failed"] += 1
                
        return stats
