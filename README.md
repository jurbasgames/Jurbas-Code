# Jurbas-Code

Script de chat por streaming com suporte a **múltiplos providers** de LLM.

Providers disponíveis:

- `claude` (padrão) — usa a **assinatura do Claude Code** (token OAuth), não a API key paga por token.
- `deepseek` — usa a API da DeepSeek via SDK compatível com OpenAI.

## Seleção de provider

Defina a variável `LLM_PROVIDER` (padrão: `claude`):

```sh
LLM_PROVIDER=claude   uv run main.py "Sua pergunta aqui"
LLM_PROVIDER=deepseek uv run main.py "Sua pergunta aqui"
```

Sem argumentos, o prompt padrão é `Hello`.

## Provider `claude` — assinatura do Claude Code

Não usa créditos da API. Em vez disso, usa o token OAuth da sua assinatura
(a mesma consumida pelo Claude Code).

Basta estar logado no Claude Code. O script lê automaticamente as credenciais
de `~/.claude/.credentials.json` (campo `claudeAiOauth.accessToken`):

1. Faça login na assinatura (uma vez), com o Claude Code instalado:

   ```sh
   claude
   ```

   Isso grava/atualiza `~/.claude/.credentials.json`. Se o token expirar,
   rode `claude` novamente para renovar.

2. (Opcional) Override manual via variável de ambiente — tem prioridade
   sobre o arquivo de credenciais:

   ```sh
   export CLAUDE_CODE_OAUTH_TOKEN=<token-gerado-com-claude-setup-token>
   ```

   Para usar outro diretório de config, defina `CLAUDE_CONFIG_DIR`.

O cliente envia o token como `Authorization: Bearer` junto do header beta
`oauth-2025-04-20`. Como esse token é escopado ao Claude Code, o script
prefixa a identidade do Claude Code no system prompt para a Messages API
aceitar a chamada.

## Provider `deepseek`

```sh
export DEEPSEEK_API_KEY=<sua-key>
LLM_PROVIDER=deepseek uv run main.py
```

## Rodando

```sh
uv run main.py "Olá, tudo bem?"
```
