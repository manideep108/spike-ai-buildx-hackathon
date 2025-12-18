"""
GA4 Data API service for fetching analytics data.
Handles authentication, query execution, and response transformation.
"""
import os 
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
)
from google.oauth2 import service_account
from config.settings import settings
from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class GA4Service:
    """Service for interacting with GA4 Data API."""
    
    def __init__(self):
        """Initialize GA4 client with credentials."""
        # Resolve the credentials path from settings
        src_dir = os.path.dirname(os.path.dirname(__file__))
        self.credentials_path = os.path.abspath(
            os.path.join(src_dir, settings.ga4_credentials_path)
        )
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Load credentials and initialize GA4 client."""
        try:
            if not os.path.exists(self.credentials_path):
                if settings.demo_mode:
                    logger.warning("DEMO MODE: GA4 credentials not found. Will use mock data.")
                    self.client = None
                    return
                raise FileNotFoundError(
                    f"GA4 credentials file not found at: {self.credentials_path}. "
                    f"Please set GA4_CREDENTIALS_PATH in .env to the correct path."
                )
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )
            self.client = BetaAnalyticsDataClient(credentials=credentials)
            logger.info("✓ GA4 Data API client initialized successfully")
        except Exception as e:
            if settings.demo_mode:
                logger.warning(f"DEMO MODE: GA4 initialization failed: {e}. Will use mock data.")
                self.client = None
            else:
                logger.error(f"Failed to initialize GA4 client: {e}")
                logger.error(f"Credentials path attempted: {self.credentials_path}")
                raise
    
    @retry_with_backoff
    def run_report(
        self,
        property_id: str,
        metrics: List[str],
        dimensions: Optional[List[str]] = None,
        start_date: str = "30daysAgo",
        end_date: str = "today",
        limit: int = 10000,
    ) -> Dict[str, Any]:
        """
        Execute a GA4 report request.
        
        Args:
            property_id: GA4 property ID
            metrics: List of metric names
            dimensions: List of dimension names
            start_date: Start date (YYYY-MM-DD or relative like '7daysAgo')
            end_date: End date (YYYY-MM-DD or 'today')
            limit: Maximum number of rows to return
        
        Returns:
            Dictionary with report data and metadata
        """
        # Demo mode: return mock data if client unavailable
        if self.client is None and settings.demo_mode:
            logger.info("📊 DEMO MODE: Returning mock GA4 analytics data")
            return self._get_mock_data(metrics, dimensions)
        
        try:
            # Build request
            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                metrics=[Metric(name=metric) for metric in metrics],
                dimensions=[Dimension(name=dim) for dim in (dimensions or [])],
                limit=limit,
            )
            
            # Execute request
            response = self.client.run_report(request)
            
            # Transform response
            return self._transform_response(response)
        
        except Exception as e:
            logger.error(f"GA4 API error: {e}")
            raise
    
    def _transform_response(self, response) -> Dict[str, Any]:
        """
        Transform GA4 API response into a structured format.
        
        Args:
            response: GA4 API response object
        
        Returns:
            Dictionary with rows, metadata, and summary
        """
        # Extract dimension and metric headers
        dimension_headers = [header.name for header in response.dimension_headers]
        metric_headers = [header.name for header in response.metric_headers]
        
        # Extract rows
        rows = []
        for row in response.rows:
            row_data = {}
            
            # Add dimensions
            for i, dim_value in enumerate(row.dimension_values):
                row_data[dimension_headers[i]] = dim_value.value
            
            # Add metrics
            for i, metric_value in enumerate(row.metric_values):
                row_data[metric_headers[i]] = metric_value.value
            
            rows.append(row_data)
        
        return {
            "rows": rows,
            "row_count": len(rows),
            "dimension_headers": dimension_headers,
            "metric_headers": metric_headers,
            "metadata": None
        }
    
    def get_default_property_id(self) -> Optional[str]:
        """Get default property ID from settings."""
        return settings.default_ga4_property_id
    
    def parse_relative_date(self, relative_date: str) -> str:
        """
        Convert relative date to YYYY-MM-DD format.
        
        Args:
            relative_date: Date like 'today', 'yesterday', '7daysAgo'
        
        Returns:
            Date in YYYY-MM-DD format
        """
        today = datetime.now().date()
        
        if relative_date == "today":
            return str(today)
        elif relative_date == "yesterday":
            return str(today - timedelta(days=1))
        elif "daysAgo" in relative_date:
            days = int(relative_date.replace("daysAgo", ""))
            return str(today - timedelta(days=days))
        else:
            # Assume it's already in YYYY-MM-DD format
            return relative_date
    
    def _get_mock_data(self, metrics: List[str], dimensions: Optional[List[str]]) -> Dict[str, Any]:
        """
        Generate realistic mock data for demo mode.
        Creates a narrative: baseline → spike (SEO fix) → regression (404s) → recovery
        """
        rows = []
        
        if dimensions and "date" in dimensions:
            # Time-series data with narrative arc
            import datetime
            today = datetime.date.today()
            
            for days_ago in range(29, -1, -1):  # Last 30 days
                date_val = (today - datetime.timedelta(days=days_ago)).strftime("%Y%m%d")
                row = {"date": date_val}
                
                # Narrative-based user counts
                if days_ago >= 23:  # Days 1-7: Baseline
                    base_users = 500
                elif days_ago >= 20:  # Days 8-10: Traffic spike (SEO fix deployed)
                    base_users = 1200
                elif days_ago >= 10:  # Days 11-20: Regression (404 errors introduced)
                    base_users = 300
                else:  # Days 21-30: Recovery
                    base_users = 800
                
                # Add some variation
                import random
                random.seed(days_ago)  # Deterministic variation
                users = int(base_users * (0.9 + random.random() * 0.2))
                
                for metric in metrics:
                    if "user" in metric.lower() or metric == "sessions":
                        row[metric] = str(users)
                    elif metric == "bounceRate":
                        # Higher bounce during regression
                        if days_ago >= 10 and days_ago < 20:
                            row[metric] = str(0.68 + random.random() * 0.10)
                        else:
                            row[metric] = str(0.42 + random.random() * 0.10)
                    elif metric == "pageViews":
                        row[metric] = str(int(users * (2.1 + random.random() * 0.6)))
                    else:
                        row[metric] = str(users)
                
                rows.append(row)
        
        elif dimensions:
            # Mock dimensional data
            mock_values = {
                "country": ["United States", "India", "United Kingdom", "Canada", "Germany"],
                "deviceCategory": ["desktop", "mobile", "tablet"],
                "city": ["New York", "London", "Mumbai", "Toronto", "Berlin"]
            }
            for i in range(5):
                row = {}
                for dim in dimensions:
                    if dim in mock_values:
                        row[dim] = mock_values[dim][i % len(mock_values[dim])]
                    else:
                        row[dim] = f"value_{i+1}"
                for metric in metrics:
                    row[metric] = str((i + 1) * 1234)
                rows.append(row)
        else:
            # Mock aggregate data (average for the period)
            row = {}
            for metric in metrics:
                if "user" in metric.lower() or metric == "sessions":
                    row[metric] = "650"  # Average across narrative
                elif metric == "bounceRate":
                    row[metric] = "0.52"  # Average
                elif metric == "pageViews":
                    row[metric] = "1560"
                else:
                    row[metric] = "650"
            rows.append(row)
        
        return {
            "rows": rows,
            "row_count": len(rows),
            "dimension_headers": dimensions or [],
            "metric_headers": metrics,
            "metadata": {"demo_mode": True, "narrative": "baseline→spike→regression→recovery"}
        }


# Global GA4 service instance
ga4_service = GA4Service()
