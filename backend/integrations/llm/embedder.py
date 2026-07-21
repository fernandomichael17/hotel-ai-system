import httpx
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class TextEmbedder:
    """
    Client embedder untuk pemrosesan embedding teks.
    Mendukung mode mock untuk pengembangan lokal guna menghemat penggunaan resource RAM/CPU.
    """
    _instance = None
    
    def __new__(cls):
        """
        Membuat atau mengembalikan instance singleton dari TextEmbedder.
        Mengecek konfigurasi use_mock_embedder untuk menentukan inisialisasi HTTP client.

        Parameters:
            Tidak ada.

        Returns:
            TextEmbedder: Instance singleton dari TextEmbedder.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.use_mock = settings.use_mock_embedder
            cls._instance.embedding_model = settings.embedding_model
            
            if not cls._instance.use_mock:
                cls._instance.client = httpx.Client(
                    base_url=settings.infinity_url,
                    timeout=30.0
                )
                logger.info("TextEmbedder diinisialisasi menggunakan Infinity server.")
            else:
                cls._instance.client = None
                logger.info("TextEmbedder diinisialisasi menggunakan Mock Embedder (768 dimensi).")
        return cls._instance

    def embed(self, text: str) -> list[float]:
        """
        Mengonversi kueri teks pengguna ke bentuk embedding.
        Menggunakan dummy vector jika mode mock aktif, atau memanggil Infinity server jika tidak.

        Parameters:
            text (str): Kueri teks pengguna yang akan diubah menjadi embedding.

        Returns:
            list[float]: Vektor embedding dari teks input berdimensi 768.
        """
        if self.use_mock:
            # Menggunakan vektor non-nol untuk menghindari pembagian dengan nol pada cosine distance di pgvector
            return [0.1] * 768
            
        prefixed = f"query: {text}"
        try:
            response = self.client.post(
                "/embeddings",
                json={
                    "model": self.embedding_model,
                    "input": [prefixed]
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"Gagal memanggil Infinity /embeddings untuk query: {str(e)}")
            raise

    def embed_passage(self, text: str) -> list[float]:
        """
        Mengonversi teks dokumen ke bentuk embedding.
        Menggunakan dummy vector jika mode mock aktif, atau memanggil Infinity server jika tidak.

        Parameters:
            text (str): Teks dokumen yang akan diubah menjadi embedding.

        Returns:
            list[float]: Vektor embedding dari teks input berdimensi 768.
        """
        if self.use_mock:
            # Menggunakan vektor non-nol untuk menghindari pembagian dengan nol pada cosine distance di pgvector
            return [0.1] * 768
            
        prefixed = f"passage: {text}"
        try:
            response = self.client.post(
                "/embeddings",
                json={
                    "model": self.embedding_model,
                    "input": [prefixed]
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"Gagal memanggil Infinity /embeddings untuk passage: {str(e)}")
            raise

    def embed_batch(
        self,
        texts: list[str],
        is_passage: bool = True,
        batch_size: int = 32
    ) -> list[list[float]]:
        """
        Mengembed kumpulan teks (batch) secara bersamaan.
        Menggunakan dummy vector jika mode mock aktif, atau memanggil Infinity server jika tidak.

        Parameters:
            texts (list[str]): Kumpulan teks yang akan diubah menjadi embedding.
            is_passage (bool): Flag penanda apakah teks berupa dokumen (True) atau kueri (False).
            batch_size (int): Ukuran batch untuk pengiriman data.

        Returns:
            list[list[float]]: Kumpulan vektor embedding berdimensi 768 yang diurutkan sesuai urutan input.
        """
        if self.use_mock:
            # Menggunakan vektor non-nol untuk menghindari pembagian dengan nol pada cosine distance di pgvector
            return [[0.1] * 768 for _ in texts]
            
        prefix = "passage: " if is_passage else "query: "
        prefixed = [f"{prefix}{t}" for t in texts]
        
        try:
            response = self.client.post(
                "/embeddings",
                json={
                    "model": self.embedding_model,
                    "input": prefixed
                }
            )
            response.raise_for_status()
            data = response.json()
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]
        except Exception as e:
            logger.error(f"Gagal memanggil Infinity /embeddings untuk batch: {str(e)}")
            raise

# Singleton instance
embedder = TextEmbedder()
