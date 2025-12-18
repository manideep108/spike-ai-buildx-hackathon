"""Quick verification script to check if paths are correct"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import settings
from config.settings import settings

print("=" * 60)
print("PATH VERIFICATION")
print("=" * 60)
print(f"Current working directory: {os.getcwd()}")
print(f"Script directory: {os.path.dirname(__file__)}")
print()
print("Settings loaded:")
print(f"  GA4 Credentials Path: {settings.ga4_credentials_path}")
print(f"  LiteLLM API Key: {settings.litellm_api_key[:20]}...")
print(f"  Sheets Spreadsheet ID: {settings.sheets_spreadsheet_id}")
print()

# Import services to test their path resolution
from services.ga4_service import GA4Service
from services.sheets_service import SheetsService

print("Service credential paths:")
# Test GA4Service path resolution
test_ga4 = GA4Service.__new__(GA4Service)
test_ga4.credentials_path = os.path.abspath(
    os.path.join(
        os.path.join(os.path.dirname(__file__), 'src', 'services'),
        settings.ga4_credentials_path
    )
)
print(f"  GA4 Service path: {test_ga4.credentials_path}")
print(f"  GA4 File exists: {os.path.exists(test_ga4.credentials_path)}")

# Test SheetsService path resolution  
test_sheets = SheetsService.__new__(SheetsService)
test_sheets.credentials_path = os.path.abspath(
    os.path.join(
        os.path.join(os.path.dirname(__file__), 'src', 'services'),
        settings.ga4_credentials_path
    )
)
print(f"  Sheets Service path: {test_sheets.credentials_path}")
print(f"  Sheets File exists: {os.path.exists(test_sheets.credentials_path)}")
print("=" * 60)
