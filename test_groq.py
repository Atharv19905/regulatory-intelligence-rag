
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {
            "role": "system",
            "content": "Answer accurately and concisely."
        },
        {
            "role": "user",
            "content": "What is RAG in two sentences?"
        }
    ],
    max_completion_tokens=200,
)

print(response.choices[0].message.content)
