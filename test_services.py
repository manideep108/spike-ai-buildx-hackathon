"""Test credentials path resolution"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("="*60)
print("Testing Credentials Path Resolution")
print("="*60)

# Import and check what paths the services actually resolve to
try:
    print("\nImporting GA4 Service...")
    from services.ga4_service import ga4_service
    print(f"  GA4 Service credentials path: {ga4_service.credentials_path}")
    print(f"  File exists: {os.path.exists(ga4_service.credentials_path)}")
    print(f"  [OK] GA4 Service initialized successfully!")
except Exception as e:
    print(f"  [ERROR] GA4 Service failed: {e}")

try:
    print("\nImporting Sheets Service...")
    from services.sheets_service import sheets_service  
    print(f"  Sheets Service credentials path: {sheets_service.credentials_path}")
    print(f"  File exists: {os.path.exists(sheets_service.credentials_path)}")
    print(f"  [OK] Sheets Service initialized successfully!")
except Exception as e:
    print(f"  [ERROR] Sheets Service failed: {e}")

print("\n" + "="*60)
print("All services initialized successfully!" if 'ga4_service' in dir() and 'sheets_service' in dir() else "Some services failed to initialize")
print("="*60)
