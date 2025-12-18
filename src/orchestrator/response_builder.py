"""
Response builder for formatting API responses.
"""

from typing import Dict, Any, Optional
import time


class ResponseBuilder:
    """Builds standardized API responses."""
    
    @staticmethod
    def build_success_response(
        answer: str,
        data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build a success response.
        
        Args:
            answer: Natural language answer
            data: Optional data payload
            metadata: Optional metadata
        
        Returns:
            Formatted response dictionary
        """
        response = {
            "success": True,
            "answer": answer,
        }
        
        if data is not None:
            response["data"] = data
        
        if metadata:
            response["metadata"] = metadata
        
        return response
    
    @staticmethod
    def build_error_response(
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build an error response.
        
        Args:
            error: Error message
            details: Optional error details
        
        Returns:
            Formatted error response
        """
        response = {
            "success": False,
            "error": error,
        }
        
        if details:
            response["details"] = details
        
        return response
    
    @staticmethod
    def add_metadata(
        response: Dict[str, Any],
        agent: str,
        execution_time: float,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add metadata to a response.
        
        Args:
            response: Response dictionary
            agent: Agent name used
            execution_time: Execution time in seconds
            additional_metadata: Optional additional metadata
        
        Returns:
            Response with metadata added
        """
        metadata = {
            "agent": agent,
            "execution_time": round(execution_time, 2),
        }
        
        if additional_metadata:
            metadata.update(additional_metadata)
        
        response["metadata"] = metadata
        return response


# Global response builder instance
response_builder = ResponseBuilder()
