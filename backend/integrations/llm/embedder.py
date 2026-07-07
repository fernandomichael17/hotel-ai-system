from sentence_transformers import SentenceTransformer
from typing import List

class TextEmbedder:
    """Embedder using sentence-transformers for multilingual-e5-base."""
    
    def __init__(self, model_name: str = "intfloat/multilingual-e5-base"):
        # Load the model
        self.model = SentenceTransformer(model_name)
        
    async def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        # Note: sentence_transformers is synchronous, we wrap it in async for the interface
        embedding = self.model.encode("query: " + text, normalize_embeddings=True)
        return embedding.tolist()
        
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of text strings."""
        # Prepend query: to texts as required by e5 models for retrieval
        formatted_texts = ["query: " + t for t in texts]
        embeddings = self.model.encode(formatted_texts, normalize_embeddings=True)
        return embeddings.tolist()
