import re
import json
from typing import List, Optional
from backend.integrations.llm.client import LLMClient
from backend.core.classifier.schemas import IntentType, IntentResult, ExtractionResult, DualIntentResult
from backend.core.classifier.prompt_templates import (
    build_classification_prompt,
    build_multiturn_prompt,
    build_extraction_prompt,
    build_dual_intent_prompt
)

class IntentClassifier:
    """
    Kelas untuk melakukan klasifikasi intent dari pesan pengguna menggunakan LLM.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Inisialisasi IntentClassifier dengan dependensi LLMClient.

        Parameters:
            llm_client (LLMClient): Klien LLM yang digunakan untuk memanggil model.
        """
        self.llm_client = llm_client

    def classify(self, message: str) -> IntentResult:
        """
        Mengklasifikasikan pesan pengguna ke salah satu dari IntentType yang didukung.

        Parameters:
            message (str): Pesan teks pengguna yang akan diklasifikasikan.

        Returns:
            IntentResult: Hasil klasifikasi berupa objek IntentResult.
        """
        prompt = build_classification_prompt(message)
        raw_response = self.llm_client.generate(prompt)

        # Hapus tag <think>...</think> beserta isinya jika model tetap menghasilkan proses berpikir (thinking)
        cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)

        # Standardisasi string ke lowercase
        cleaned_response = cleaned_response.strip().lower()

        # Konversi spasi ke underscore jika model menghasilkan format tanpa underscore
        cleaned_response = cleaned_response.replace("booking inquiry", "booking_inquiry")
        cleaned_response = cleaned_response.replace("booking request", "booking_request")

        # Bersihkan tanda baca, tanda kurung, dan karakter markdown
        for char in [".", ",", '"', "'", "`", "-", ">", "*", ":", "(", ")", "[", "]"]:
            cleaned_response = cleaned_response.replace(char, " ")

        # Pisahkan menjadi kata-kata terpisah untuk mencari intent yang cocok
        words = cleaned_response.split()

        intent = IntentType.UNKNOWN
        confidence = 0.0

        for word in words:
            try:
                matched = IntentType(word)
                if matched != IntentType.UNKNOWN:
                    intent = matched
                    confidence = 1.0
                    break
            except ValueError:
                continue

        return IntentResult(
            intent=intent,
            confidence=confidence,
            raw_response=raw_response
        )

    def classify_multiturn(self, history: List[dict], message: str) -> IntentResult:
        """
        Mengklasifikasikan intent dari pesan terbaru dengan mempertimbangkan riwayat percakapan sebelumnya.

        Parameters:
            history (List[dict]): Daftar pesan percakapan sebelumnya [{"role": "user"|"assistant", "content": str}].
            message (str): Pesan terbaru pengguna.

        Returns:
            IntentResult: Hasil klasifikasi intent terbaru beserta tingkat kepercayaan.
        """
        prompt = build_multiturn_prompt(history, message)
        raw_response = self.llm_client.generate(prompt)

        # Hapus tag <think>...</think>
        cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)
        cleaned_response = cleaned_response.strip().lower()

        cleaned_response = cleaned_response.replace("booking inquiry", "booking_inquiry")
        cleaned_response = cleaned_response.replace("booking request", "booking_request")

        for char in [".", ",", '"', "'", "`", "-", ">", "*", ":", "(", ")", "[", "]"]:
            cleaned_response = cleaned_response.replace(char, " ")

        words = cleaned_response.split()
        intent = IntentType.UNKNOWN
        confidence = 0.0

        for word in words:
            try:
                matched = IntentType(word)
                if matched != IntentType.UNKNOWN:
                    intent = matched
                    confidence = 1.0
                    break
            except ValueError:
                continue

        return IntentResult(
            intent=intent,
            confidence=confidence,
            raw_response=raw_response
        )

    def classify_dual(self, message: str) -> DualIntentResult:
        """
        Mendeteksi satu atau dua intent sekaligus dari satu kalimat pesan pengguna.

        Parameters:
            message (str): Pesan teks pengguna yang akan dianalisis.

        Returns:
            DualIntentResult: Hasil klasifikasi berisi daftar intent yang ditemukan.
        """
        prompt = build_dual_intent_prompt(message)
        raw_response = self.llm_client.generate(prompt)

        # Hapus tag <think>
        cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)
        cleaned_response = cleaned_response.strip().lower()

        # Konversi format spasi ke underscore untuk intent bermultikata sebelum diproses koma
        cleaned_response = cleaned_response.replace("booking inquiry", "booking_inquiry")
        cleaned_response = cleaned_response.replace("booking request", "booking_request")

        # Pisahkan menggunakan tanda koma
        tokens = cleaned_response.split(",")

        intents = []
        for token in tokens:
            # Bersihkan karakter non-alphanumeric (kecuali underscore) dari tiap token intent
            cleaned_token = token.strip()
            for char in [".", '"', "'", "`", "-", ">", "*", ":", "(", ")", "[", "]"]:
                cleaned_token = cleaned_token.replace(char, " ")
            
            words_in_token = cleaned_token.split()
            for word in words_in_token:
                try:
                    matched = IntentType(word)
                    if matched != IntentType.UNKNOWN and matched not in intents:
                        intents.append(matched)
                except ValueError:
                    continue

        if not intents:
            intents.append(IntentType.UNKNOWN)

        return DualIntentResult(
            intents=intents,
            raw_response=raw_response
        )


class ParameterExtractor:
    """
    Kelas untuk mengekstraksi parameter pemesanan seperti nama, tipe kamar, dan tanggal dari pesan pengguna.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """
        Inisialisasi ParameterExtractor dengan dependensi LLMClient.

        Parameters:
            llm_client (LLMClient): Klien LLM yang digunakan untuk memanggil model.
        """
        self.llm_client = llm_client

    def extract(self, message: str) -> ExtractionResult:
        """
        Mengekstrak parameter entitas pemesanan dari pesan pengguna.

        Parameters:
            message (str): Pesan teks pengguna yang berisi informasi pemesanan.

        Returns:
            ExtractionResult: Hasil ekstraksi parameter dalam bentuk objek terstruktur.
        """
        prompt = build_extraction_prompt(message)
        raw_response = self.llm_client.generate(prompt)

        # Hapus tag <think>
        cleaned = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)
        cleaned = cleaned.strip()

        # Bersihkan pembungkus markdown ```json ... ``` jika ada
        markdown_match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned, re.DOTALL)
        if markdown_match:
            cleaned = markdown_match.group(1).strip()

        try:
            data = json.loads(cleaned)
            name = data.get("name")
            check_in = data.get("check_in_date")
            check_out = data.get("check_out_date")
            room_type = data.get("room_type")
        except Exception:
            name, check_in, check_out, room_type = None, None, None, None

        # Ubah tipe data jika output bukan string agar tetap konsisten
        def stringify(val) -> Optional[str]:
            if val is None:
                return None
            return str(val)

        return ExtractionResult(
            name=stringify(name),
            check_in_date=stringify(check_in),
            check_out_date=stringify(check_out),
            room_type=stringify(room_type),
            raw_response=raw_response
        )
