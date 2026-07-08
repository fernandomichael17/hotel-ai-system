from sentence_transformers import SentenceTransformer
from backend.config import settings
import numpy as np

class TextEmbedder:
    """
    Singleton embedder untuk menghasilkan representasi vektor (embeddings) dari teks.
    
    Menggunakan library sentence-transformers dengan model lokal yang di-load 
    sekali saat inisialisasi awal aplikasi demi optimalisasi performa komputasi.
    """
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._model = SentenceTransformer(
                settings.embedding_model,
                trust_remote_code=True
            )
        return cls._instance
    
    def embed(self, text: str) -> list[float]:
        """
        Mengonversi kueri teks pengguna ke dalam bentuk embedding 768 dimensi.
        
        Secara otomatis menambahkan prefix 'query: ' untuk model retrieval.
        """
        prefixed = f"query: {text}"
        embedding = self._model.encode(
            prefixed,
            normalize_embeddings=True
        )
        return embedding.tolist()
    
    def embed_passage(self, text: str) -> list[float]:
        """
        Mengonversi teks dokumen ke dalam bentuk embedding 768 dimensi.
        
        Secara otomatis menambahkan prefix 'passage: ' untuk dokumen penjelas.
        """
        prefixed = f"passage: {text}"
        embedding = self._model.encode(
            prefixed,
            normalize_embeddings=True
        )
        return embedding.tolist()
    
    def embed_batch(
        self,
        texts: list[str],
        is_passage: bool = True,
        batch_size: int = 32
    ) -> list[list[float]]:
        """
        Mengembed kumpulan teks secara bersamaan untuk mempercepat proses tokenisasi berkas RAG.
        """
        prefix = "passage: " if is_passage else "query: "
        prefixed = [f"{prefix}{t}" for t in texts]
        
        embeddings = self._model.encode(
            prefixed,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 10
        )
        return embeddings.tolist()

# Singleton instance
embedder = TextEmbedder()
