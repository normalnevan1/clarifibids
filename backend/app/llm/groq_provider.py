from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel
from app.core.config import settings

class LLMResponse(BaseModel):
    content: str
    model_name: str
    provider: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: float

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.1, 
        max_tokens: int = 512
    ) -> LLMResponse:
        pass

class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        
    async def generate(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.1, 
        max_tokens: int = 512
    ) -> LLMResponse:
        if not self.api_key or self.api_key.startswith("gsk_placeholder"):
            raise ValueError(
                "Real GROQ_API_KEY is missing in backend/.env. Please configure your actual Groq API key."
            )
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Groq API returned error {response.status_code}: {response.text}")
                
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=content,
                model_name=self.model_name,
                provider="groq",
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                latency_ms=0.0
            )

def get_llm_provider() -> BaseLLMProvider:
    if settings.LLM_PROVIDER.lower() == "groq":
        return GroqProvider(api_key=settings.GROQ_API_KEY, model_name=settings.GROQ_MODEL)
    raise NotImplementedError(f"Provider {settings.LLM_PROVIDER} not supported in current MVP.")
