import os
import httpx

def _load_env_file() -> None:
    """
    Membaca file .env secara manual dari root project dan memuatnya ke os.environ.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(current_dir, "../../.."))
    env_path = os.path.join(root_dir, ".env")

    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip().strip("'\""))
        except Exception:
            pass

# Muat file .env secara otomatis saat modul diimpor
_load_env_file()

class LLMClient:
    """
    Klien untuk berkomunikasi dengan model LLM menggunakan API yang kompatibel dengan OpenAI.
    """

    def __init__(self) -> None:
        """
        Inisialisasi LLMClient dengan konfigurasi dari environment variables.
        """
        api_base = os.getenv("LLM_API_BASE")
        if not api_base:
            base_url = os.getenv("LLM_BASE_URL", "http://localhost:8000")
            if not base_url.rstrip("/").endswith("/v1"):
                api_base = f"{base_url.rstrip('/')}/v1"
            else:
                api_base = base_url

        self.api_base = api_base.rstrip("/")
        self.model_name = os.getenv("LLM_MODEL_NAME") or os.getenv("MODEL_NAME", "hotel-llm")
        self.api_key = os.getenv("LLM_API_KEY")
        # Menggunakan satu instance client untuk menggunakan kembali koneksi TCP (Connection Pool)
        self.client = httpx.Client(timeout=30.0)

    def generate(self, prompt: str) -> str:
        """
        Mengirimkan prompt ke model LLM dan mengembalikan respons teks.

        Parameters:
            prompt (str): Prompt teks yang akan dikirim ke model.

        Returns:
            str: Konten teks hasil respons dari model.

        Raises:
            ValueError: Jika respons dari model kosong atau tidak valid.
            ConnectionError: Jika terjadi masalah koneksi saat menghubungi server model.
        """
        url = f"{self.api_base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            # Menambahkan parameter untuk menonaktifkan thinking pada model vLLM (seperti Qwen)
            "chat_template_kwargs": {
                "enable_thinking": False
            }
        }

        try:
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.RequestError as exc:
            raise ConnectionError(f"Gagal terhubung ke LLM server di {url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ConnectionError(f"HTTP error terjadi saat menghubungi LLM server: {exc}") from exc

        data = response.json()
        if not data or "choices" not in data or not data["choices"]:
            raise ValueError("Respons dari LLM kosong atau format tidak valid.")

        choice = data["choices"][0]
        content = choice.get("message", {}).get("content", "")
        if not content or not content.strip():
            raise ValueError("Respons dari LLM kosong.")

        return content.strip()
