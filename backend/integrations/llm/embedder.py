import httpx
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class TextEmbedder:
    """
    Client embedder yang terhubung ke server TEI (Text Embeddings Inference) eksternal.
    Menghilangkan beban komputasi lokal dan load model ke RAM server utama.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tei_url = settings.tei_url
            cls._instance.client = httpx.Client(
                base_url=settings.tei_url,
                timeout=30.0
            )
            logger.info(f"TextEmbedder diinisialisasi untuk menggunakan TEI server di: {settings.tei_url}")
        return cls._instance

    def embed(self, text: str) -> list[float]:
        """
        Mengonversi kueri teks pengguna ke bentuk embedding via TEI server.
        Menambahkan prefix 'query: ' untuk model retrieval.
        """
        prefixed = f"query: {text}"
        try:
            response = self.client.post("/embed", json={"inputs": prefixed})
            response.raise_for_status()
            return response.json()[0]
        except Exception as e:
            logger.error(f"Gagal memanggil TEI /embed untuk query: {str(e)}")
            raise

    def embed_passage(self, text: str) -> list[float]:
        """
        Mengonversi teks dokumen ke bentuk embedding via TEI server.
        Menambahkan prefix 'passage: ' untuk dokumen penjelas.
        """
        prefixed = f"passage: {text}"
        try:
            response = self.client.post("/embed", json={"inputs": prefixed})
            response.raise_for_status()
            return response.json()[0]
        except Exception as e:
            logger.error(f"Gagal memanggil TEI /embed untuk passage: {str(e)}")
            raise

    def embed_batch(
        self,
        texts: list[str],
        is_passage: bool = True,
        batch_size: int = 32
    ) -> list[list[float]]:
        """
        Mengembed kumpulan teks (batch) secara bersamaan melalui server TEI.
        """
        prefix = "passage: " if is_passage else "query: "
        prefixed = [f"{prefix}{t}" for t in texts]
        
        try:
            response = self.client.post("/embed", json={"inputs": prefixed})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Gagal memanggil TEI /embed untuk batch: {str(e)}")
            raise

# Singleton instance
embedder = TextEmbedder()
