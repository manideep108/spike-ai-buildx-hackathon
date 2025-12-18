"""
Configuration management using pydantic-settings.
Loads environment variables and provides centralized settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path
import os

# Dynamically find the .env file
# When running from src/, go up one level; when running from root, stay here
def find_env_file() -> str:
    """Find the .env file in project root."""
    current_dir = Path(__file__).parent  # config directory
    src_dir = current_dir.parent  # src directory  
    project_root = src_dir.parent  # project root
    
    env_path = project_root / ".env"
    if env_path.exists():
        return str(env_path)
    
    # Fallback to relative path
    return "../.env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # LiteLLM Configuration (Hackathon Proxy)
    litellm_api_key: str  # HACKATHON_API_KEY
    litellm_base_url: str = "http://3.110.18.218"
    litellm_model: str = "gemini-2.5-flash"
    
    # GA4 Configuration
    ga4_credentials_path: str = "../credentials.json"
    default_ga4_property_id: Optional[str] = None
    
    # Google Sheets Configuration
    sheets_spreadsheet_id: Optional[str] = None
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    
    # Retry Configuration
    max_retries: int = 3
    retry_min_wait: int = 1
    retry_max_wait: int = 10
    
    # Demo Mode
    demo_mode: bool = False


# Global settings instance
settings = Settings()
