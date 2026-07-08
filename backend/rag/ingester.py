import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from backend.integrations.llm.embedder import embedder
from backend.db.repositories.document_repo import DocumentRepository

CHUNK_SIZE = 400      # karakter per chunk
CHUNK_OVERLAP = 50    # overlap antar chunk

logger = logging.getLogger(__name__)

class DocumentIngester:
    """Modul untuk memotong dokumen, menghasilkan vektor embedding, dan menyimpannya di database RAG."""
    
    def __init__(self, db: AsyncSession):
        self.repo = DocumentRepository(db)
        
    async def ingest_file(
        self,
        file_path: str,
        hotel_id: str,
        title: str
    ) -> int:
        """Mengekstraksi file PDF/DOCX/TXT dan melakukan penyimpanan data chunks."""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Gagal ingest dokumen, berkas tidak ditemukan: {file_path}")
            raise FileNotFoundError(
                f"File tidak ditemukan: {file_path}"
            )
            
        logger.info(f"Memulai proses RAG ingest untuk file: {file_path}")
        text = self._parse_with_docling(file_path)
        logger.info(f"Parsing berkas selesai. Panjang teks: {len(text)} karakter.")
        
        return await self.ingest_text(
            text=text,
            hotel_id=hotel_id,
            title=title,
            source_file=path.name
        )
        
    async def ingest_text(
        self,
        text: str,
        hotel_id: str,
        title: str,
        source_file: str = "manual"
    ) -> int:
        """Mengolah teks mentah ke dalam db RAG."""
        chunks = self._chunk_text(text)
        if not chunks:
            logger.warning(f"Isi teks dokumen '{title}' kosong, mengabaikan proses ingest.")
            return 0
            
        logger.info(f"Menghasilkan {len(chunks)} chunks untuk teks '{title}'. Memulai ekstraksi embedding...")
        embeddings = embedder.embed_batch(
            chunks,
            is_passage=True
        )
        
        logger.info(f"Pembersihan chunks lama untuk source_file: '{source_file}' milik hotel_id: {hotel_id}")
        await self.repo.delete_by_source(
            hotel_id=hotel_id,
            source_file=source_file
        )
        
        logger.info(f"Melakukan penyimpanan {len(chunks)} data chunks baru...")
        documents = [
            {
                "hotel_id": hotel_id,
                "title": title,
                "content": chunk,
                "embedding": embedding,
                "source_file": source_file,
                "chunk_index": i
            }
            for i, (chunk, embedding)
            in enumerate(zip(chunks, embeddings))
        ]
        
        count = await self.repo.bulk_create(documents)
        logger.info(f"Proses ingest '{title}' selesai. Berhasil menyimpan {count} data chunks.")
        return count
        
    def _parse_with_docling(
        self,
        file_path: str
    ) -> str:
        """Mem-parse berkas dokumen menggunakan Docling Converter (untuk PDF/DOCX) atau langsung (untuk TXT)."""
        path = Path(file_path)
        
        if path.suffix.lower() == ".txt":
            return path.read_text(encoding="utf-8")
            
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(file_path)
            return result.document.export_to_markdown()
        except Exception as e:
            logger.error(f"Error saat mengekstraksi berkas dengan Docling: {str(e)}")
            raise ValueError(
                f"Gagal parse dokumen: {str(e)}"
            )
            
    def _chunk_text(
        self,
        text: str,
        chunk_size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP
    ) -> list[str]:
        """Memecah teks panjang menjadi potongan kecil dengan batasan overlap secara presisi."""
        if not text or not text.strip():
            return []
            
        paragraphs = text.split("\n\n")
        elements = []
        
        for p in paragraphs:
            if len(p) > chunk_size:
                sentences = p.split(". ")
                for s in sentences:
                    s_strip = s.strip()
                    if s_strip:
                        if not s_strip.endswith("."):
                            s_strip += "."
                        elements.append(s_strip)
            else:
                p_strip = p.strip()
                if p_strip:
                    elements.append(p_strip)
                    
        chunks = []
        current_chunk = ""
        
        for el in elements:
            if not current_chunk:
                current_chunk = el
            elif len(current_chunk) + len(el) + 1 <= chunk_size:
                current_chunk += " " + el
            else:
                if len(current_chunk) >= 50:
                    chunks.append(current_chunk)
                
                if overlap > 0 and len(current_chunk) > overlap:
                    overlap_text = current_chunk[-overlap:]
                    space_idx = overlap_text.find(" ")
                    if space_idx != -1:
                        overlap_text = overlap_text[space_idx:].strip()
                    current_chunk = overlap_text + " " + el
                else:
                    current_chunk = el
                    
        if current_chunk and len(current_chunk) >= 50:
            chunks.append(current_chunk)
            
        return chunks
