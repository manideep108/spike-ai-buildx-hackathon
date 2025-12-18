# Credentials Path Fix - Summary

## Problem
The application was failing to start with the error:
```
FileNotFoundError: [Errno 2] No such file or directory: 'credentials.json'
```

## Root Cause
The deploy script runs `cd src && python -m uvicorn main:app`, which:
1. Changes the working directory to `src/`
2. Makes relative paths resolve from `src/` instead of the project root
3. The `credentials.json` file is in the project root, not in `src/`

## Solution
Made two key changes:

### 1. Updated `.env` file
Changed the credentials path to use a relative path from the `src` directory:
```diff
- GA4_CREDENTIALS_PATH=credentials.json
+ GA4_CREDENTIALS_PATH=../credentials.json
```

### 2. Updated `src/config/settings.py`
- Added a `find_env_file()` function to dynamically locate the `.env` file in the project root
- Changed the default `ga4_credentials_path` to `../credentials.json`
- This ensures the settings work correctly regardless of where the application is run from

## Verification
Created `verify_paths.py` to test path resolution:
- ✅ `.env` file is found and loaded correctly
- ✅ All environment variables are read properly
- ✅ `credentials.json` path resolves correctly from the `src` directory
- ✅ File exists check passes

## How to Run

### Option 1: Git Bash (Unix-style)
```bash
bash deploy.sh
```

### Option 2: Windows Batch File
```cmd
deploy.bat
```

### Option 3: Direct Command
```bash
cd src
python -m uvicorn main:app --host 0.0.0.0 --port 8080
```

## Files Modified
1. `.env` - Updated `GA4_CREDENTIALS_PATH`
2. `src/config/settings.py` - Added dynamic path resolution
3. `verify_paths.py` - Created for testing (optional)
4. `deploy.bat` - Created for Windows users (new)

## Result
The server should now start successfully and be able to access the Google credentials file! 🎉
