import os
import logging
from openai import OpenAI, OpenAIError

logging.basicConfig(level=logging.INFO)

def main():
    client = OpenAI(
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com"
    )

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

    if response.choices:
        print(response.choices[0].message.content)
    else:
        logging.warning("No choices returned in the response.")
except OpenAIError as e:
    logging.error(f"API error occurred: {e}")
except Exception as e:
    logging.error(f"An unexpected error occurred: {e}")
        print("Error: No response choices returned from the API.")

if __name__ == '__main__':
    main()
