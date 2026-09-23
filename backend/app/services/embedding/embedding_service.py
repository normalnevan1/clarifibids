import os
import sys
from abc import ABC, abstractmethod
from typing import List

# Check if sentence-transformers is available
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

class BaseEmbeddingService(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass
        
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass

class BGESmallEmbeddingService(BaseEmbeddingService):
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None
        
    def _get_model(self):
        if self._model is None:
            if not HAS_SENTENCE_TRANSFORMERS:
                raise RuntimeError("sentence-transformers is not installed. Please install it in your environment.")
            self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model
        
    def embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        # BGE models recommend query prefix for retrieval, but for generic chunks we embed directly
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
        
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=16)
        return embeddings.tolist()

embedding_service = BGESmallEmbeddingService()
