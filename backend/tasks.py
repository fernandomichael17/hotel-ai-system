import os
import asyncio
import logging
from celery import Celery
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.rag.ingester import DocumentIngester

logger = logging.getLogger(__name__)

# 1. Inisialisasi Celery App
celery_app = Celery(
    "hotel_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
)

def run_async_coro(coro):
    """
    Menjalankan coroutine asinkronus secara sinkronus di dalam thread saat ini.
    
    Parameter:
        coro: Objek coroutine yang akan dijalankan.
        
    Return:
        Hasil eksekusi dari coroutine yang dipanggil.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(coro)

@celery_app.task(name="backend.tasks.ingest_document")
def ingest_document(file_path: str, hotel_id: str, title: str):
    """
    Task latar belakang Celery untuk memproses ekstraksi file dokumen ke basis data RAG.
    
    Parameter:
        file_path (str): Path berkas dokumen temporary.
        hotel_id (str): ID unik hotel pemilik dokumen.
        title (str): Judul dokumen yang akan disimpan.
        
    Return:
        dict: Hasil pemrosesan berisi status dan jumlah chunk yang dibuat.
    """
    logger.info(f"Memulai background task Celery untuk ingest berkas: {file_path}")
    
    async def _execute():
        async with AsyncSessionLocal() as db:
            ingester = DocumentIngester(db)
            return await ingester.ingest_file(
                file_path=file_path,
                hotel_id=hotel_id,
                title=title
            )
            
    try:
        count = run_async_coro(_execute())
        logger.info(f"Sukses mengolah {count} chunks untuk dokumen {title} via Celery.")
        return {"status": "success", "chunks_created": count}
    except Exception as e:
        logger.error(f"Gagal melakukan ingest dokumen {title} via Celery: {str(e)}", exc_info=True)
        return {"status": "failed", "error": str(e)}
    finally:
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
                logger.info(f"Berhasil membersihkan berkas temporary: {file_path}")
            except Exception as ex:
                logger.error(f"Gagal menghapus berkas temporary {file_path}: {str(ex)}")
