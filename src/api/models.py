"""
Data models for the API.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """
    Request model for the query endpoint.
    """
    query: str = Field(
        ..., 
        description="Natural language query string",
        min_length=3,
        max_length=1000,
        example="Compare analytics for last month vs this month"
    )
    propertyId: Optional[str] = Field(
        None,
        description="Google Analytics 4 Property ID",
        example="123456789"
    )
    spreadsheetId: Optional[str] = Field(
        None,
        description="Google Sheets Spreadsheet ID",
        example="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    )


class QueryResponse(BaseModel):
    """
    Response model for the query endpoint.
    """
    success: bool = Field(..., description="Whether the query was processed successfully")
    answer: Optional[str] = Field(None, description="Natural language answer")
    data: Optional[Dict[str, Any] | List[Any]] = Field(None, description="Structured data returned by agents")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (execution time, confidence, etc)")


# OpenAI Compatible Models

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "gemini-2.5-flash"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class ChatCompletionResponse(BaseModel):
    """Response model for /chat/completions endpoint."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, int]] = None
