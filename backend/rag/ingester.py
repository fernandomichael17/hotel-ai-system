from typing import List
import uuid
from docling.document_converter import DocumentConverter
from ..db.database import AsyncSessionLocal
from ..db.repositories.document_repo import DocumentRepository
from ..integrations.llm.embedder import TextEmbedder

class DocumentIngester:
    """Ingester for parsing, chunking, and embedding documents."""
    
    def __init__(self, embedder: TextEmbedder):
        self.embedder = embedder
        self.converter = DocumentConverter()
        
    def _chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        # Simple word-based chunking as approximation for tokens for now
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += (chunk_size - overlap)
        return chunks
        
    async def ingest_file(self, file_path: str, hotel_id: str, title: str) -> int:
        """Parse file with Docling and ingest."""
        result = self.converter.convert(file_path)
        text_content = result.document.export_to_markdown()
        
        return await self.ingest_text(
            text=text_content,
            hotel_id=hotel_id,
            title=title,
            source_file=file_path
        )
        
    async def ingest_text(self, text: str, hotel_id: str, title: str, source_file: str = "manual") -> int:
        """Ingest raw text."""
        chunks = self._chunk_text(text)
        
        if not chunks:
            return 0
            
        # Get embeddings for all chunks in batch
        embeddings = await self.embedder.embed_batch(chunks)
        
        async with AsyncSessionLocal() as db_session:
            repo = DocumentRepository(db_session)
            
            for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                await repo.create({
                    "hotel_id": uuid.UUID(hotel_id),
                    "title": title,
                    "content": chunk_text,
                    "embedding": embedding,
                    "source_file": source_file,
                    "chunk_index": idx
                })
                
        return len(chunks)
