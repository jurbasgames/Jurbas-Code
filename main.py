import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")

messages = [
    {"role": "system", "content": "You are Jurbas Code, a code assistant."}
]

while True:
    user_input = input("You: ").strip()
    if user_input.lower() in ("exit", "quit"):
        break
    if not user_input:
        continue

    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=messages,
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )

    reply = response.choices[0].message.content.strip()
    print(f"AI: {reply}\n")
    messages.append({"role": "assistant", "content": reply})
