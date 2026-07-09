from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import Document
from backend.config import settings

class DocumentRepository:
    """Repository untuk mengelola dokumen/knowledge base RAG."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def find_by_id(self, id: UUID) -> Optional[Document]:
        """Mencari dokumen berdasarkan UUID."""
        result = await self.db.execute(
            select(Document).where(Document.id == id)
        )
        return result.scalar_one_or_none()
        
    async def find_by_hotel(self, hotel_id: UUID, active_only: bool = True) -> List[Document]:
        """Mencari semua dokumen milik hotel tertentu."""
        stmt = select(Document).where(Document.hotel_id == hotel_id)
        if active_only:
            stmt = stmt.where(Document.is_active == True)
        stmt = stmt.order_by(Document.title, Document.chunk_index)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
        
    async def find_by_source_file(self, hotel_id: UUID, source_file: str) -> List[Document]:
        """Mencari dokumen berdasarkan nama berkas sumber aslinya."""
        result = await self.db.execute(
            select(Document).where(
                Document.hotel_id == hotel_id,
                Document.source_file == source_file
            )
        )
        return list(result.scalars().all())
        
    async def get_source_files(self, hotel_id: UUID) -> List[str]:
        """Mendapatkan daftar nama file sumber unik yang terdaftar aktif."""
        result = await self.db.execute(
            select(Document.source_file)
            .where(Document.hotel_id == hotel_id, Document.is_active == True)
            .distinct()
        )
        return [row for row in result.scalars().all() if row is not None]
        
    async def create(self, hotel_id: UUID, title: str, content: str, 
                     embedding: List[float], source_file: str, chunk_index: int) -> Document:
        """Membuat satu dokumen baru."""
        doc = Document(
            hotel_id=hotel_id,
            title=title,
            content=content,
            embedding=embedding,
            source_file=source_file,
            chunk_index=chunk_index
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc
        
    async def bulk_create(self, documents: List[dict]) -> int:
        """Menambahkan banyak dokumen secara batch sekaligus."""
        if not documents:
            return 0
        db_docs = [Document(**doc) for doc in documents]
        self.db.add_all(db_docs)
        await self.db.commit()
        return len(db_docs)
        
    async def deactivate_by_source(self, hotel_id: UUID, source_file: str) -> int:
        """Menonaktifkan secara soft-delete semua dokumen dari file sumber tertentu."""
        stmt = update(Document).where(
            Document.hotel_id == hotel_id,
            Document.source_file == source_file
        ).values(is_active=False)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
        
    async def delete_by_source(self, hotel_id: UUID, source_file: str) -> int:
        """Menghapus secara permanen semua dokumen dari file sumber tertentu (hard-delete)."""
        stmt = delete(Document).where(
            Document.hotel_id == hotel_id,
            Document.source_file == source_file
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
        
    async def similarity_search(self, query_embedding: List[float], hotel_id: UUID, 
                                top_k: int = 5, min_score: float = 0.5) -> List[dict]:
        """Melakukan pencarian dokumen RAG menggunakan pgvector operator (<=>)."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            cosine_dist = Document.embedding.cosine_distance(query_embedding)
            score = 1.0 - cosine_dist
            stmt = (
                select(
                    Document.id,
                    Document.title,
                    Document.content,
                    score.label("score")
                )
                .where(Document.hotel_id == hotel_id, Document.is_active == True)
                .order_by(cosine_dist)
                .limit(top_k)
            )
            result = await self.db.execute(stmt)
            rows = result.all()
        except Exception as e:
            logger.error(f"Error saat melakukan similarity_search pgvector: {str(e)}", exc_info=True)
            return []
            
        docs = []
        for row in rows:
            score_val = float(row.score) if row.score is not None else 0.0
            if score_val >= min_score:
                docs.append({
                    "id": row.id,
                    "title": row.title,
                    "content": row.content,
                    "score": score_val
                })
        return docs

def get_document_repo(db: AsyncSession) -> DocumentRepository:
    """Helper Dependency Injection untuk DocumentRepository di FastAPI."""
    return DocumentRepository(db)
