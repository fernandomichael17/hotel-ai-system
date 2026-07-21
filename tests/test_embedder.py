import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Menambahkan root directory ke sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.integrations.llm.embedder import TextEmbedder

class TestTextEmbedder(unittest.TestCase):
    """
    Kelas pengujian untuk memverifikasi fungsionalitas kelas TextEmbedder.
    """

    @patch("backend.integrations.llm.embedder.httpx.Client")
    def setUp(self, mock_client_class):
        """
        Menyiapkan objek mock client HTTP sebelum menjalankan setiap pengujian.

        Parameters:
            mock_client_class (MagicMock): Mock kelas httpx.Client.

        Returns:
            Tidak ada.
        """
        # Reset singleton instance untuk testing agar dapat menginjeksikan mock client
        TextEmbedder._instance = None
        self.mock_client = MagicMock()
        mock_client_class.return_value = self.mock_client
        self.embedder = TextEmbedder()
        self.embedder.client = self.mock_client

    def test_embed_success(self):
        """
        Memastikan fungsi embed berhasil mengirimkan request dengan payload yang benar
        dan mengembalikan representasi vektor embedding yang valid ketika mode mock tidak aktif.

        Parameters:
            Tidak ada.

        Returns:
            Tidak ada.
        """
        # Matikan mode mock secara eksplisit untuk test HTTP client
        self.embedder.use_mock = False
        
        # Konfigurasi mock response untuk endpoint /embeddings
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3], "index": 0}
            ]
        }
        self.mock_client.post.return_value = mock_response

        # Eksekusi fungsi embed
        result = self.embedder.embed("test query")

        # Verifikasi hasil
        self.assertEqual(result, [0.1, 0.2, 0.3])
        self.mock_client.post.assert_called_once_with(
            "/embeddings",
            json={
                "model": self.embedder.embedding_model,
                "input": ["query: test query"]
            }
        )

    def test_embed_passage_success(self):
        """
        Memastikan fungsi embed_passage berhasil mengirimkan request dengan prefix 'passage:'
        dan mengembalikan representasi vektor embedding yang valid ketika mode mock tidak aktif.

        Parameters:
            Tidak ada.

        Returns:
            Tidak ada.
        """
        # Matikan mode mock secara eksplisit untuk test HTTP client
        self.embedder.use_mock = False

        # Konfigurasi mock response untuk endpoint /embeddings
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.4, 0.5, 0.6], "index": 0}
            ]
        }
        self.mock_client.post.return_value = mock_response

        # Eksekusi fungsi embed_passage
        result = self.embedder.embed_passage("test passage")

        # Verifikasi hasil
        self.assertEqual(result, [0.4, 0.5, 0.6])
        self.mock_client.post.assert_called_once_with(
            "/embeddings",
            json={
                "model": self.embedder.embedding_model,
                "input": ["passage: test passage"]
            }
        )

    def test_embed_batch_success(self):
        """
        Memastikan fungsi embed_batch berhasil mengirimkan request dalam bentuk list/batch
        dan mengembalikan kumpulan vektor embedding sesuai urutan input ketika mode mock tidak aktif.

        Parameters:
            Tidak ada.

        Returns:
            Tidak ada.
        """
        # Matikan mode mock secara eksplisit untuk test HTTP client
        self.embedder.use_mock = False

        # Konfigurasi mock response untuk batch input.
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.7, 0.8, 0.9], "index": 1},
                {"embedding": [0.1, 0.2, 0.3], "index": 0}
            ]
        }
        self.mock_client.post.return_value = mock_response

        # Eksekusi fungsi embed_batch
        result = self.embedder.embed_batch(["text 1", "text 2"], is_passage=True)

        # Verifikasi hasil diurutkan berdasarkan index
        self.assertEqual(result, [[0.1, 0.2, 0.3], [0.7, 0.8, 0.9]])
        self.mock_client.post.assert_called_once_with(
            "/embeddings",
            json={
                "model": self.embedder.embedding_model,
                "input": ["passage: text 1", "passage: text 2"]
            }
        )

    def test_mock_embed_success(self):
        """
        Memastikan fungsi embed mengembalikan vektor dummy 768 dimensi saat mode mock aktif.

        Parameters:
            Tidak ada.

        Returns:
            Tidak ada.
        """
        self.embedder.use_mock = True
        result = self.embedder.embed("test query")
        self.assertEqual(len(result), 768)
        self.assertEqual(result, [0.1] * 768)

    def test_mock_embed_passage_success(self):
        """
        Memastikan fungsi embed_passage mengembalikan vektor dummy 768 dimensi saat mode mock aktif.

        Parameters:
            Tidak ada.

        Returns:
            Tidak ada.
        """
        self.embedder.use_mock = True
        result = self.embedder.embed_passage("test passage")
        self.assertEqual(len(result), 768)
        self.assertEqual(result, [0.1] * 768)

    def test_mock_embed_batch_success(self):
        """
        Memastikan fungsi embed_batch mengembalikan list vektor dummy 768 dimensi saat mode mock aktif.

        Parameters:
            Tidak ada.

        Returns:
            Tidak ada.
        """
        self.embedder.use_mock = True
        result = self.embedder.embed_batch(["text 1", "text 2"])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [0.1] * 768)
        self.assertEqual(result[1], [0.1] * 768)

if __name__ == "__main__":
    unittest.main()
