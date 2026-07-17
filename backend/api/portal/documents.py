import os
import tempfile
import logging
import asyncio
from fastapi import (
    APIRouter, Depends, UploadFile,
    File, HTTPException, BackgroundTasks
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.api.portal.auth import (
    get_current_hotel, TokenData
)
from backend.rag.ingester import DocumentIngester
from backend.db.repositories.document_repo import (
    DocumentRepository
)
from backend.tasks import ingest_document

router = APIRouter()
logger = logging.getLogger(__name__)

class DocumentResponse(BaseModel):
    id: str
    title: str
    source_file: str
    chunk_count: int
    created_at: str

class UploadResponse(BaseModel):
    success: bool
    message: str
    chunks_created: int
    source_file: str

class TestFAQRequest(BaseModel):
    question: str

class TestFAQResponse(BaseModel):
    question: str
    answer: str
    sources_used: int
    context_preview: str

@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    List semua dokumen aktif untuk hotel ini.
    Group by source_file dan hitung chunk_count.
    """
    from sqlalchemy import select, func, cast, String
    from backend.db.models import Document
    from uuid import UUID
    
    try:
        stmt = (
            select(
                func.min(cast(Document.id, String)).label("id"),
                Document.title,
                Document.source_file,
                func.count(Document.id).label("chunk_count"),
                func.max(Document.created_at).label("created_at")
            )
            .where(
                Document.hotel_id == UUID(current_hotel.hotel_id),
                Document.is_active == True
            )
            .group_by(Document.source_file, Document.title)
            .order_by(func.max(Document.created_at).desc())
        )
        result = await db.execute(stmt)
        rows = result.all()
    except Exception as e:
        logger.error(f"Gagal mengambil daftar dokumen: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal memproses daftar dokumen")
        
    return [
        DocumentResponse(
            id=str(row.id),
            title=row.title,
            source_file=row.source_file or "unknown",
            chunk_count=row.chunk_count,
            created_at=row.created_at.isoformat() if row.created_at else ""
        )
        for row in rows
    ]

@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload dokumen knowledge base dan jalankan ingest di latar belakang menggunakan Celery.
    """
    ALLOWED_TYPES = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt"
    }
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Validasi type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Format tidak didukung. Gunakan PDF, DOCX, atau TXT."
        )
    
    # Baca dan validasi ukuran
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File terlalu besar. Maksimal 10MB."
        )
    
    # Format title dari nama file
    title = file.filename\
        .rsplit(".", 1)[0]\
        .replace("_", " ")\
        .replace("-", " ")\
        .title()
    
    # Pastikan direktori temporary bersama ada
    os.makedirs("backend/tmp", exist_ok=True)
    
    # Simpan ke temp file di bawah direktori bersama
    suffix = ALLOWED_TYPES[file.content_type]
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        dir="backend/tmp"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    # Pemicu background task Celery (Offline Process)
    ingest_document.delay(tmp_path, current_hotel.hotel_id, title)
    logger.info(f"Mendaftarkan task Celery untuk memproses dokumen {title} (path: {tmp_path})")
    
    return UploadResponse(
        success=True,
        message=f"Dokumen '{title}' sedang diproses. Refresh halaman dalam 30 detik.",
        chunks_created=0,
        source_file=file.filename
    )

@router.delete("/documents/{source_file}")
async def delete_document(
    source_file: str,
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    Hapus semua chunks dokumen berdasarkan nama file asal milik hotel yang login.
    """
    from uuid import UUID
    repo = DocumentRepository(db)
    
    try:
        count = await repo.delete_by_source(
            hotel_id=UUID(current_hotel.hotel_id),
            source_file=source_file
        )
    except Exception as e:
        logger.error(f"Gagal menghapus dokumen {source_file}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal menghapus dokumen")
    
    if count == 0:
        raise HTTPException(
            status_code=404,
            detail="Dokumen tidak ditemukan atau sudah terhapus"
        )
    
    return {
        "success": True,
        "message": f"Dokumen dihapus ({count} chunks)"
    }

@router.post("/documents/test-faq", response_model=TestFAQResponse)
async def test_faq(
    request: TestFAQRequest,
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    Menguji kecocokan kueri RAG secara instan menggunakan model LLM lokal.
    """
    from backend.rag.retriever import RAGRetriever
    from backend.core.workflows.faq.handler import (
        FAQ_SYSTEM_PROMPT,
        FAQ_USER_PROMPT
    )
    from backend.integrations.llm.client import get_llm_client
    
    retriever = RAGRetriever(db)
    
    # 1. Get context
    try:
        results = await retriever.retrieve(
            query=request.question,
            hotel_id=current_hotel.hotel_id,
            top_k=4
        )
    except Exception as e:
        logger.error(f"Error retrieve RAG di test-faq: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal melakukan retrieve kueri")
    
    if not results:
        return TestFAQResponse(
            question=request.question,
            answer="Informasi tidak ditemukan di knowledge base. Coba upload dokumen yang relevan.",
            sources_used=0,
            context_preview=""
        )
    
    # 2. Build context string
    context = "\n\n".join([
        f"[{r['title']}]\n{r['content']}"
        for r in results
    ])
    
    # 3. Generate answer
    llm = get_llm_client()
    system = FAQ_SYSTEM_PROMPT.format(
        hotel_name=current_hotel.hotel_name
    )
    user_msg = FAQ_USER_PROMPT.format(
        context=context,
        question=request.question
    )
    
    # Menggabungkan ke satu string tunggal karena LLMClient hanya mendukung .generate(prompt)
    prompt_parts = [
        f"Instruksi Asisten:\n{system}\n",
        user_msg
    ]
    final_prompt = "\n".join(prompt_parts)
    
    try:
        answer = await asyncio.to_thread(llm.generate, final_prompt)
    except Exception as e:
        logger.error(f"Gagal memanggil model LLM di test-faq: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal memproses jawaban model LLM")
    
    return TestFAQResponse(
        question=request.question,
        answer=answer,
        sources_used=len(results),
        context_preview=context[:300] + "..." if len(context) > 300 else context
    )
