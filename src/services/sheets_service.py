"""
Google Sheets service for reading SEO data.
Uses same credentials.json for authentication.
"""

import os
import logging
from typing import Optional, Dict, Any, List
import gspread
from google.oauth2 import service_account
from config.settings import settings

logger = logging.getLogger(__name__)


class SheetsService:
    """Service for interacting with Google Sheets API."""
    
    def __init__(self):
        """Initialize Google Sheets client with credentials."""
        # Resolve the credentials path from settings
        src_dir = os.path.dirname(os.path.dirname(__file__))
        self.credentials_path = os.path.abspath(
            os.path.join(src_dir, settings.ga4_credentials_path)
        )
        self.spreadsheet_id = settings.sheets_spreadsheet_id
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Load credentials and initialize Sheets client."""
        try:
            if not os.path.exists(self.credentials_path):
                if settings.demo_mode:
                    logger.warning("DEMO MODE: Sheets credentials not found. Will use mock data.")
                    self.client = None
                    return
                raise FileNotFoundError(
                    f"Sheets credentials file not found at: {self.credentials_path}. "
                    f"Please set GA4_CREDENTIALS_PATH in .env to the correct path."
                )
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets.readonly",
                    "https://www.googleapis.com/auth/drive.readonly",
                ],
            )
            self.client = gspread.authorize(credentials)
            logger.info("✓ Google Sheets API client initialized successfully")
        except Exception as e:
            if settings.demo_mode:
                logger.warning(f"DEMO MODE: Sheets initialization failed: {e}. Will use mock data.")
                self.client = None
            else:
                logger.error(f"Failed to initialize Sheets client: {e}")
                logger.error(f"Credentials path attempted: {self.credentials_path}")
                raise
    
    def read_sheet(
        self,
        spreadsheet_id: Optional[str] = None,
        sheet_name: Optional[str] = None,
        sheet_index: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Read data from a Google Sheet.
        
        Args:
            spreadsheet_id: Spreadsheet ID (uses default if not provided)
            sheet_name: Name of the sheet/tab to read
            sheet_index: Index of the sheet (0-based) if name not provided
        
        Returns:
            List of dictionaries representing rows
        """
        # Demo mode: return mock data if client unavailable
        if self.client is None and settings.demo_mode:
            logger.info("📄 DEMO MODE: Returning mock SEO/Sheets data")
            return self._get_mock_seo_data()
        
        try:
            # Use provided spreadsheet_id or default from settings
            sheet_id = spreadsheet_id or self.spreadsheet_id
            
            if not sheet_id:
                raise ValueError("No spreadsheet ID provided and no default configured")
            
            # Open spreadsheet
            spreadsheet = self.client.open_by_key(sheet_id)
            
            # Get worksheet
            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(sheet_index)
            
            # Get all records as list of dictionaries
            data = worksheet.get_all_records()
            
            logger.info(f"✓ Successfully read {len(data)} rows from Google Sheets")
            return data
        
        except Exception as e:
            logger.error(f"Error reading sheet: {e}")
            raise
    
    def filter_data(
        self,
        data: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Filter data based on conditions.
        
        Args:
            data: List of row dictionaries
            filters: Dictionary of column->value filters
        
        Returns:
            Filtered list of rows
        """
        filtered = data
        
        for column, value in filters.items():
            filtered = [
                row for row in filtered
                if column in row and str(row[column]).lower() == str(value).lower()
            ]
        
        return filtered
    
    def aggregate_data(
        self,
        data: List[Dict[str, Any]],
        group_by: Optional[str] = None,
        aggregate_column: Optional[str] = None,
        operation: str = "count",
    ) -> Dict[str, Any]:
        """
        Aggregate data with grouping.
        
        Args:
            data: List of row dictionaries
            group_by: Column to group by
            aggregate_column: Column to aggregate
            operation: 'count', 'sum', 'avg', 'min', 'max'
        
        Returns:
            Aggregated results
        """
        if not group_by:
            # No grouping, just count
            return {"total": len(data)}
        
        # Group data
        groups = {}
        for row in data:
            key = str(row.get(group_by, "Unknown"))
            if key not in groups:
                groups[key] = []
            groups[key].append(row)
        
        # Aggregate
        results = {}
        for key, group in groups.items():
            if operation == "count":
                results[key] = len(group)
            elif aggregate_column:
                values = [
                    float(row.get(aggregate_column, 0))
                    for row in group
                    if row.get(aggregate_column)
                ]
                
                if operation == "sum":
                    results[key] = sum(values)
                elif operation == "avg":
                    results[key] = sum(values) / len(values) if values else 0
                elif operation == "min":
                    results[key] = min(values) if values else 0
                elif operation == "max":
                    results[key] = max(values) if values else 0
        
        return results
    
    def get_column_names(
        self,
        spreadsheet_id: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> List[str]:
        """
        Get column names from a sheet.
        
        Args:
            spreadsheet_id: Spreadsheet ID
            sheet_name: Sheet name
        
        Returns:
            List of column names
        """
        try:
            sheet_id = spreadsheet_id or self.spreadsheet_id
            spreadsheet = self.client.open_by_key(sheet_id)
            
            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)
            
            # Get first row (headers)
            headers = worksheet.row_values(1)
            return headers
        
        except Exception as e:
            logger.error(f"Error getting column names: {e}")
            raise
    
    def _get_mock_seo_data(self) -> List[Dict[str, Any]]:
        """Generate realistic mock SEO data for demo mode."""
        return [
            {"URL": "https://example.com/", "Status Code": "200", "Title": "Homepage", "Meta Description": "Welcome to our site", "H1": "Home"},
            {"URL": "https://example.com/products", "Status Code": "200", "Title": "Products", "Meta Description": "Our products", "H1": "Products"},
            {"URL": "https://example.com/about", "Status Code": "404", "Title": "About Us", "Meta Description": "", "H1": "About"},
            {"URL": "https://example.com/contact", "Status Code": "200", "Title": "Contact Us - Very Long Title That Exceeds Recommended Length", "Meta Description": "Get in touch", "H1": "Contact"},
            {"URL": "https://example.com/blog", "Status Code": "200", "Title": "Blog", "Meta Description": "Read our blog", "H1": "Blog"}
        ]


# Global Sheets service instance
sheets_service = SheetsService()
