"""
Validation utilities for user inputs and API requests.
"""

import re
from typing import Optional


def validate_property_id(property_id: str) -> bool:
    """
    Validate GA4 property ID format.
    Should be numeric and reasonable length.
    """
    if not property_id:
        return False
    
    # Property IDs are typically numeric strings
    if not re.match(r'^\d+$', property_id):
        return False
    
    # Reasonable length check (GA4 property IDs are usually 9-10 digits)
    if len(property_id) < 5 or len(property_id) > 15:
        return False
    
    return True


def sanitize_query(query: str) -> str:
    """
    Sanitize user query by removing potentially harmful characters.
    Preserves alphanumeric, spaces, and common punctuation.
    """
    if not query:
        return ""
    
    # Remove excessive whitespace
    query = " ".join(query.split())
    
    # Remove control characters but keep printable ones
    query = "".join(char for char in query if char.isprintable() or char.isspace())
    
    return query.strip()


def validate_query_length(query: str) -> tuple[bool, str]:
    """
    Validate query meets minimum length requirements.
    
    Args:
        query: The sanitized query string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not query or len(query.strip()) == 0:
        return False, "Query cannot be empty"
    
    if len(query.strip()) < 3:
        return False, "Query must contain at least 3 non-whitespace characters"
    
    return True, ""


def validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> bool:
    """
    Validate date format (YYYY-MM-DD).
    """
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    
    if start_date and not re.match(date_pattern, start_date):
        return False
    
    if end_date and not re.match(date_pattern, end_date):
        return False
    
    return True


def validate_spreadsheet_id(spreadsheet_id: str) -> bool:
    """
    Validate Google Sheets spreadsheet ID format.
    Should be alphanumeric with hyphens and underscores.
    """
    if not spreadsheet_id:
        return False
    
    # Google Sheets IDs are alphanumeric with hyphens/underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', spreadsheet_id):
        return False
    
    # Typical length check
    if len(spreadsheet_id) < 20 or len(spreadsheet_id) > 100:
        return False
    
    return True
