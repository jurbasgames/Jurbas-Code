import json
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # carrega variaveis do .env (CLAUDE_CODE_OAUTH_TOKEN, DEEPSEEK_API_KEY, LLM_PROVIDER)

DEFAULT_SYSTEM = "You are a helpful assistant"
DEFAULT_PROMPT = "Hello"

# Identidade exigida para usar o token OAuth da assinatura do Claude Code
# na Messages API (o token é escopado ao Claude Code).
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."
CLAUDE_CODE_USER_AGENT = "claude-cli/2.1.183 (external, cli)"
ANTHROPIC_VERSION = "2023-06-01"
CLAUDE_CODE_BETA_FLAGS = (
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "redact-thinking-2026-02-12",
    "thinking-token-count-2026-05-13",
    "context-management-2025-06-27",
    "prompt-caching-scope-2026-01-05",
    "mid-conversation-system-2026-04-07",
    "advisor-tool-2026-03-01",
    "advanced-tool-use-2025-11-20",
    "effort-2025-11-24",
    "extended-cache-ttl-2025-04-11",
    "cache-diagnosis-2026-04-07",
)


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


def claude_config_dir():
    """Diretorio de config do Claude Code (~/.claude, ou CLAUDE_CONFIG_DIR)."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".claude"


def load_claude_code_token():
    """Le o access token OAuth de ~/.claude/.credentials.json.

    Esse e o token da assinatura do Claude Code, gravado ao logar com
    `claude` (campo claudeAiOauth.accessToken). Retorna None se ausente.
    """
    creds_path = claude_config_dir() / ".credentials.json"
    try:
        data = json.loads(creds_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Aviso: nao foi possivel ler {creds_path}: {exc}", file=sys.stderr)
        return None

    oauth = data.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not token:
        return None

    # expiresAt vem em milissegundos; avisa (mas nao bloqueia) se expirado.
    expires_at = oauth.get("expiresAt")
    if isinstance(expires_at, (int, float)) and expires_at / 1000 < time.time():
        print(
            "Aviso: o token do Claude Code em ~/.claude parece expirado. "
            "Rode `claude` para renovar a sessao.",
            file=sys.stderr,
        )
    return token


def resolve_claude_token():
    """CLAUDE_CODE_OAUTH_TOKEN (override) ou as credenciais de ~/.claude."""
    return os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or load_claude_code_token()


def claude_code_headers():
    """Headers capturados do binario interativo do Claude Code.

    Invariante de billing: OAuth do Claude Code + `x-app: cli` deve continuar
    roteando para a assinatura, nao para API billing.
    """
    return {
        "User-Agent": CLAUDE_CODE_USER_AGENT,
        "X-Claude-Code-Session-Id": str(uuid.uuid4()),
        "X-Stainless-Arch": "x64",
        "X-Stainless-Lang": "js",
        "X-Stainless-OS": "Linux",
        "X-Stainless-Package-Version": "0.94.0",
        "X-Stainless-Retry-Count": "0",
        "X-Stainless-Runtime": "node",
        "X-Stainless-Runtime-Version": "v24.3.0",
        "X-Stainless-Timeout": "600",
        "anthropic-beta": ",".join(CLAUDE_CODE_BETA_FLAGS),
        "anthropic-dangerous-direct-browser-access": "true",
        "anthropic-version": ANTHROPIC_VERSION,
        "x-app": "cli",
        "x-client-request-id": str(uuid.uuid4()),
    }


def stream_claude(system, prompt):
    """Claude usando a assinatura do Claude Code (token OAuth, não API key)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY esta setado; remova para evitar API billing. "
            "Este provider usa a assinatura do Claude Code via OAuth + x-app: cli."
        )

    import anthropic

    token = resolve_claude_token()
    if not token:
        raise RuntimeError(
            "Nao encontrei credenciais do Claude Code. Faca login com `claude` "
            "(gera ~/.claude/.credentials.json) ou defina CLAUDE_CODE_OAUTH_TOKEN."
        )

    # auth_token -> Authorization: Bearer ***; headers abaixo reproduzem o
    # trafego real capturado do `claude` interativo.
    client = anthropic.Anthropic(
        auth_token=token,
        default_headers=claude_code_headers(),
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
