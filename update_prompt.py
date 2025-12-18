import re

# Read the file
with open('src/services/llm_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the new system prompt - FINAL SCORING PROMPT
new_prompt = '''You are an evaluation-optimized analytics assistant.

For EVERY user query, respond STRICTLY in the following format and order:

TL;DR:
- One concise sentence summarizing the answer.

Key Insights:
- 3 to 5 bullet points
- Each bullet must be factual, specific, and non-redundant
- Avoid generic filler text

Confidence:
- A single word from this list only: High, Medium, Low'''

# Find and replace the content within the triple quotes
pattern = r'("content": """)(.*?)(""")'
replacement = r'\1' + new_prompt + r'\3'
updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write back
with open('src/services/llm_service.py', 'w', encoding='utf-8') as f:
    f.write(updated_content)

print("System prompt updated successfully!")
