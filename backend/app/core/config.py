from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:nevan123*@127.0.0.1:5432/clarifibids_db"
    SYNC_DATABASE_URL: str = "postgresql+psycopg://postgres:nevan123*@127.0.0.1:5432/clarifibids_db"
    
    # LLM
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    
    # Embeddings
    EMBEDDING_PROVIDER: str = "sentence_transformers"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384
    
    # Retrieval & CRAG Experimental Starting Values
    TOP_K: int = 4
    RELEVANCE_THRESHOLD: float = 0.65
    SUFFICIENCY_THRESHOLD: float = 0.70
    MAX_RETRIEVAL_ATTEMPTS: int = 2
    MAX_CONTEXT_TOKENS: int = 3000
    MAX_OUTPUT_TOKENS: int = 512
    
    # Auth
    AUTH_ENABLED: bool = False
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
