
import asyncio
import sys
import os

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.llm_service import llm_service

async def verify():
    print("Testing LLM Service Formatting...")
    try:
        response = llm_service.chat_completion([{"role": "user", "content": "Hello"}])
        print("\nResponse received:")
        print("-" * 50)
        print(response)
        print("-" * 50)
        
        # simple check
        if "TL;DR" in response and "Key Insights" in response and "Confidence" in response:
            print("\n✅ Verification SUCCESS: Response format matches requirements.")
        else:
            print("\n❌ Verification FAILED: Response missing required sections.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
