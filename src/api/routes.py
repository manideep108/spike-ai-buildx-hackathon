"""
FastAPI routes for the multi-agent backend.
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, status
from api.models import QueryRequest, QueryResponse, ChatCompletionRequest, ChatCompletionResponse, ChatMessage
from orchestrator.orchestrator import orchestrator
from utils.validators import sanitize_query, validate_property_id, validate_query_length
from services.llm_service import llm_service
import time

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    """
    Process a natural language query using the multi-agent system.
    
    Args:
        request: Query request with query text and optional property ID
    
    Returns:
        Query response with answer and data
    
    Raises:
        HTTPException: If validation fails or processing errors occur
    """
    # Generate unique request ID for tracking
    request_id = uuid.uuid4().hex
    logger.info(f"[{request_id}] Received query request")
    
    try:
        # Sanitize query
        clean_query = sanitize_query(request.query)
        logger.info(f"[{request_id}] Sanitized query: '{clean_query[:100]}'")
        
        # Validate query length
        is_valid, error_message = validate_query_length(clean_query)
        if not is_valid:
            logger.warning(f"[{request_id}] Query validation failed: {error_message}")
            return QueryResponse(
                success=False,
                error=error_message,
                answer=None,
                data=None,
                metadata={
                    "request_id": request_id,
                    "error_code": "INVALID_QUERY"
                }
            )
        
        # Validate property ID if provided
        if request.propertyId:
            if not validate_property_id(request.propertyId):
                logger.warning(f"[{request_id}] Invalid property ID format: {request.propertyId}")
                return QueryResponse(
                    success=False,
                    error="Invalid GA4 property ID format. Property ID should be numeric and 9-12 digits.",
                    answer=None,
                    data=None,
                    metadata={
                        "request_id": request_id,
                        "error_code": "INVALID_PROPERTY_ID"
                    }
                )
        
        # Process query through orchestrator
        logger.info(f"[{request_id}] Processing query through orchestrator")
        result = await orchestrator.process_query(
            query=clean_query,
            property_id=request.propertyId,
            spreadsheet_id=request.spreadsheetId,
            request_id=request_id,
        )
        
        # Add request ID to metadata
        if result.get("metadata"):
            result["metadata"]["request_id"] = request_id
        else:
            result["metadata"] = {"request_id": request_id}
        
        logger.info(f"[{request_id}] Query processed successfully")
        
        # Return response
        return QueryResponse(**result)
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"[{request_id}] Query endpoint error: {e}", exc_info=True)
        return QueryResponse(
            success=False,
            error=f"Internal server error: {str(e)}",
            answer=None,
            data=None,
            metadata={
                "request_id": request_id,
                "error_code": "INTERNAL_ERROR"
            }
        )


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """
    OpenAI-compatible chat completions endpoint with Anti-Gravity system prompt injection.
    """
    request_id = uuid.uuid4().hex
    logger.info(f"[{request_id}] Received chat completion request for model {request.model}")

    try:
        # Extract messages
        input_messages = [{"role": m.role, "content": m.content} for m in request.messages]
        
        # Call LLM service which has the system prompt injection logic
        # Note: input_messages will be prepended with the system prompt inside chat_completion
        
        response_content = llm_service.chat_completion(
            messages=input_messages,
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens,
            json_mode=False 
        )

        # Construct OpenAI-compatible response
        return ChatCompletionResponse(
            id=f"chatcmpl-{request_id}",
            created=int(time.time()),
            model=request.model,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    },
                    "finish_reason": "stop"
                }
            ],
            usage={
                "prompt_tokens": -1, # Token counting not implemented
                "completion_tokens": -1,
                "total_tokens": -1
            }
        )

    except Exception as e:
        logger.error(f"[{request_id}] Chat completion error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "spike-ai-hackathon",
    }
