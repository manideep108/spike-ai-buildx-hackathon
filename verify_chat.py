
import requests
import json
import time
import sys

def test_chat_completions():
    url = "http://localhost:8080/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer any-token"
    }
    payload = {
        "model": "gemini-2.5-flash",
        "messages": [
            {"role": "user", "content": "What does a 200 HTTP status code mean?"}
        ]
    }

    try:
        print(f"Sending request to {url}...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
            
            content = data['choices'][0]['message']['content']
            required_terms = ["TL;DR", "Key Insights", "Confidence"]
            missing = [term for term in required_terms if term not in content]
            
            if not missing:
                print("SUCCESS: All required terms found in response.")
                return True
            else:
                print(f"FAILURE: Missing terms: {missing}")
                return False
        else:
            print(f"Error Response: {response.text}")
            return False

    except Exception as e:
        print(f"Request failed: {e}")
        return False

if __name__ == "__main__":
    # Wait a bit for server to effectively restart if reload is on, though we aren't triggering reload explicitly unless file watch does it.
    # Assuming server is managed externally or needs manual start. 
    # We'll just run the test.
    if test_chat_completions():
        sys.exit(0)
    else:
        sys.exit(1)
