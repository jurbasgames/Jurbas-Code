import os
import logging
from openai import OpenAI, OpenAIError

logging.basicConfig(level=logging.INFO)

client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")

try:
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )

    print(response.choices[0].message.content)
except OpenAIError as e:
    logging.error(f"API error occurred: {e}")
except Exception as e:
    logging.error(f"An unexpected error occurred: {e}")
