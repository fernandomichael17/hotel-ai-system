from ....rag.retriever import RAGRetriever
from ....integrations.llm.client import LLMClient
from ...channel.schemas import HotelContext, GuestContext
from ...session.manager import SessionManager

class FAQHandler:
    """Handler for FAQ workflows using RAG."""
    
    def __init__(self, llm_client: LLMClient, retriever: RAGRetriever, session_manager: SessionManager):
        self.llm_client = llm_client
        self.retriever = retriever
        self.session_manager = session_manager
        
    async def handle(self, message: str, hotel_context: HotelContext, guest_context: GuestContext, session_id: str) -> str:
        # Retrieve relevant context
        docs = await self.retriever.retrieve(message, hotel_context.hotel_id)
        
        # Format context
        context_text = "\n\n".join([f"Konteks:\n{d['content']}" for d in docs])
        
        prompt = f"""Anda adalah asisten virtual untuk {hotel_context.hotel_name}.
Tugas Anda adalah menjawab pertanyaan pengguna berdasarkan konteks yang diberikan.
Jika jawabannya tidak ada di dalam konteks, mohon sampaikan bahwa Anda tidak tahu dan tawarkan untuk menghubungi staf hotel.
Gunakan bahasa yang sopan dan profesional.

Konteks:
{context_text}

Pertanyaan Pengguna:
{message}

Jawaban:"""

        response = self.llm_client.generate(prompt)
        return response
