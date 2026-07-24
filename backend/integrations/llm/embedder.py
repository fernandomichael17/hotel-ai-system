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

    def _mock_vector(self, text: str) -> list[float]:
        """
        Menghasilkan vektor 768-dimensi berbasis hash deterministik dan pemetaan kata kunci untuk mode mock.

        Parameter:
            text (str): Teks kueri atau passage.

        Return:
            list[float]: Vektor 768-dimensi ter-normalisasi L2.
        """
        import math
        import hashlib
        
        h = hashlib.md5(text.lower().encode('utf-8')).hexdigest()
        seed = int(h[:8], 16)
        vec = [(0.05 + ((seed * (i + 1) * 31) % 100) / 1000.0) for i in range(768)]
        
        keyword_dim_map = {
            "deluxe": 10, "suite": 11, "standard": 12, "harga": 13, "kamar": 14, "850": 15,
            "kolam": 20, "renang": 21, "06.00": 22, "22.00": 23, "wifi": 30,
            "gratis": 31, "hewan": 40, "peliharaan": 41, "check-in": 50, "14.00": 51,
            "check-out": 60, "12.00": 61, "sarapan": 70, "gym": 80, "fitness": 81,
            "ballroom": 90, "500": 91, "kapasitas": 92, "cancellation": 100, "cancel": 101, "denda": 102,
            "refund": 110, "7": 111, "14": 112, "parkir": 120, "smoking": 130, "rokok": 131,
            "antar": 140, "jemput": 141, "bandara": 142, "tamu": 150, "tambahan": 151, "100.000": 152,
            "late": 160, "dekorasi": 170, "350.000": 171, "jakarta": 180, "monas": 181,
            "lokasi": 182, "meeting": 190
        }
        
        words = text.lower().split()
        for w in words:
            w_clean = w.strip(".,!?\"'()")
            if w_clean in keyword_dim_map:
                dim_idx = keyword_dim_map[w_clean]
                vec[dim_idx] += 2.0
                
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
            
        return vec

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
            return self._mock_vector(text)
            
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
            return self._mock_vector(text)
            
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
            return [self._mock_vector(t) for t in texts]
            
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
