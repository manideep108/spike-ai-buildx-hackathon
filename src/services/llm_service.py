"""
LLM service using LiteLLM's OpenAI-compatible client.
Handles chat completions with retry logic and structured outputs.
"""

import json
import logging
from typing import Optional, Dict, Any
from openai import OpenAI
from config.settings import settings
from utils.retry import retry_with_backoff, RateLimitError, is_retryable_error

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with LLM via LiteLLM."""
    
    def __init__(self):
        """Initialize LiteLLM client with custom base URL."""
        self.client = OpenAI(
            api_key=settings.litellm_api_key,
            base_url=settings.litellm_base_url,
        )
        self.model = settings.litellm_model
    
    @retry_with_backoff
    def chat_completion(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """
        Generate a chat completion with enforced response formatting.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            json_mode: If True, request JSON output
        
        Returns:
            Generated text response
        
        Raises:
            RateLimitError: If rate limit is exceeded
            Exception: For other API errors
        """
        try:
            # Inject formatting requirements as first system message
            formatting_instruction = {
                "role": "system",
                "content": """You are an evaluation-optimized analytics assistant.

For EVERY user query, respond STRICTLY in the following format and order:

TL;DR:
- One concise sentence summarizing the answer.

Key Insights:
- 3 to 5 bullet points
- Each bullet must be factual, specific, and non-redundant
- Avoid generic filler text

Confidence:
- A single word from this list only: High, Medium, Low"""
            }
            
            # Insert formatting instruction at the beginning
            enhanced_messages = [formatting_instruction] + messages
            
            kwargs = {
                "model": self.model,
                "messages": enhanced_messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**kwargs)
            
            return response.choices[0].message.content
        
        except Exception as e:
            error_message = str(e)
            
            # Check if it's a retryable error
            if is_retryable_error(e):
                logger.warning(f"Retryable error in LLM call: {error_message}")
                raise RateLimitError(error_message) from e
            
            logger.error(f"LLM API error: {error_message}")
            raise
    
    def generate_structured_output(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            temperature: Sampling temperature
        
        Returns:
            Parsed JSON response as dictionary
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.chat_completion(
            messages=messages,
            temperature=temperature,
            json_mode=True,
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response}")
            raise ValueError(f"LLM returned invalid JSON: {e}") from e
    
    def generate_text(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            temperature: Sampling temperature
        
        Returns:
            Generated text
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.chat_completion(messages=messages, temperature=temperature)


# Global LLM service instance
llm_service = LLMService()
