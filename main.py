import os
import sys

from dotenv import load_dotenv

load_dotenv()  # carrega variaveis do .env (CLAUDE_CODE_OAUTH_TOKEN, DEEPSEEK_API_KEY, LLM_PROVIDER)

DEFAULT_SYSTEM = "You are a helpful assistant"
DEFAULT_PROMPT = "Hello"

# Identidade exigida para usar o token OAuth da assinatura do Claude Code
# na Messages API (o token é escopado ao Claude Code).
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."


def stream_deepseek(system, prompt):
    """DeepSeek via SDK compatível com OpenAI (usa DEEPSEEK_API_KEY)."""
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )

    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            yield reasoning
        elif delta.content is not None:
            yield delta.content


def stream_claude(system, prompt):
    """Claude usando a assinatura do Claude Code (token OAuth, não API key)."""
    import anthropic

    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "Defina CLAUDE_CODE_OAUTH_TOKEN com o token da sua assinatura do "
            "Claude Code. Gere com: claude setup-token"
        )

    # auth_token -> Authorization: Bearer <token>; o header beta habilita OAuth.
    client = anthropic.Anthropic(
        auth_token=token,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=16000,
        system=[
            {"type": "text", "text": CLAUDE_CODE_IDENTITY},
            {"type": "text", "text": system},
        ],
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": "high"},
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                if event.delta.type == "thinking_delta":
                    yield event.delta.thinking
                elif event.delta.type == "text_delta":
                    yield event.delta.text


PROVIDERS = {
    "deepseek": stream_deepseek,
    "claude": stream_claude,
}


def main():
    provider = os.environ.get("LLM_PROVIDER", "claude").lower()
    if provider not in PROVIDERS:
        sys.exit(
            f"Provider desconhecido: {provider!r}. "
            f"Opções: {', '.join(PROVIDERS)} (defina LLM_PROVIDER)."
        )

    prompt = " ".join(sys.argv[1:]) or DEFAULT_PROMPT

    for text in PROVIDERS[provider](DEFAULT_SYSTEM, prompt):
        print(text, end="", flush=True)
    print()


if __name__ == '__main__':
    main()
