from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.channel.context import ConversationContext
from backend.core.workflows.faq.retriever import FAQRetriever
from backend.core.response.templates import FAQ_NO_RESULT
from backend.integrations.llm.client import LLMClient

FAQ_SYSTEM_PROMPT = """Kamu adalah asisten hotel {hotel_name} yang membantu tamu dengan informasi hotel.

ATURAN:
1. Jawab HANYA berdasarkan konteks yang diberikan — jangan mengarang
2. Kalau tidak ada di konteks → katakan tidak tahu dan sarankan hubungi staff
3. Jawab dalam Bahasa Indonesia yang ramah dan profesional
4. Jawaban singkat dan langsung ke inti
5. Maksimal 3 paragraf pendek
6. Jangan sebut "berdasarkan konteks" atau "dalam dokumen" — jawab natural seolah kamu tahu informasinya"""

FAQ_USER_PROMPT = """Konteks informasi hotel:
{context}

Pertanyaan tamu: {question}

Jawaban:"""

class FAQHandler:
    """FAQ workflow handler untuk memproses percakapan FAQ menggunakan LLM dan RAG."""
    
    def __init__(self, db: AsyncSession):
        self.retriever = FAQRetriever(db)
        self.llm = LLMClient()
    
    async def handle(
        self,
        ctx: ConversationContext
    ) -> str:
        """
        Memproses pesan FAQ dengan menarik dokumen pendukung dan mengirimnya ke LLM.
        """
        question = ctx.message.content
        
        # 1. Get RAG context
        context = await self.retriever.get_context(
            question=question,
            hotel_id=ctx.hotel_id
        )
        
        # 2. Tidak ada di knowledge base
        if not context:
            return FAQ_NO_RESULT.format(
                phone="(021) 1234-5678",
                email="info@hotel.com"
            )
        
        # 3. Build prompt
        system = FAQ_SYSTEM_PROMPT.format(
            hotel_name=ctx.hotel.hotel_name
        )
        user_msg = FAQ_USER_PROMPT.format(
            context=context,
            question=question
        )
        
        # 4. Gabungkan instruksi sistem, histori pesan, dan kueri saat ini ke satu prompt tunggal
        prompt_parts = [
            f"Instruksi Asisten:\n{system}\n",
        ]
        
        if ctx.history:
            prompt_parts.append("Riwayat Percakapan:")
            for msg in ctx.history:
                role_label = "Tamu" if msg.get("role") == "user" else "Asisten"
                prompt_parts.append(f"{role_label}: {msg.get('content')}")
            prompt_parts.append("")
            
        prompt_parts.append(user_msg)
        final_prompt = "\n".join(prompt_parts)
        
        # 5. Generate via LLM menggunakan asyncio.to_thread karena generate() sinkronus
        import asyncio
        response = await asyncio.to_thread(self.llm.generate, final_prompt)
        
        return response
