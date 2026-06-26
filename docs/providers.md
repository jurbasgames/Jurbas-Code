# Provider Configuration and Model Selection

Jurbas-Code supports multiple LLM providers. Currently, `claude` and `deepseek` are available. This document details how to configure them and how model selection is resolved.

## Claude Provider Setup (Default)

The `claude` provider uses Anthropic's models but is uniquely designed to use your **Claude Code CLI subscription** instead of standard Anthropic API billing.

1. Ensure you have authenticated with the official Claude Code CLI by running `claude` in your terminal.
2. Jurbas-Code will automatically read the OAuth token from `~/.claude/.credentials.json`.
3. To enforce billing guardrails, ensure `ANTHROPIC_API_KEY` is not set in your environment. If it is set, Jurbas-Code will refuse to initialize the Claude client.

**Overrides:**
- Set `CLAUDE_CONFIG_DIR` if your Claude configuration is not in `~/.claude`.
- Set `CLAUDE_CODE_OAUTH_TOKEN` to explicitly pass the token instead of reading from the file.

## DeepSeek Provider Setup

The `deepseek` provider uses DeepSeek's OpenAI-compatible API endpoints.

1. Ensure you have a DeepSeek API key.
2. Set the `DEEPSEEK_API_KEY` environment variable.
3. Run Jurbas-Code with `LLM_PROVIDER=deepseek`.

```bash
export DEEPSEEK_API_KEY="your-api-key"
LLM_PROVIDER=deepseek uv run main.py
```

## Model Selection Logic

Jurbas-Code dynamically determines the model to use based on a strict resolution hierarchy:

1. **Provider-Specific Overrides**:
   - `CLAUDE_MODEL` (if `LLM_PROVIDER=claude`)
   - `DEEPSEEK_MODEL` (if `LLM_PROVIDER=deepseek`)
2. **Global Fallback**:
   - `LLM_MODEL`
3. **API Listing & Validation**:
   - If no environment variables are set, the application checks the provider's API for available models (`client.models.list()`).
4. **Defaults**:
   - For Claude: `claude-sonnet-4-6`
   - For DeepSeek: `deepseek-v4-flash`
   - If the default model is found in the API's listed models, it is used. Otherwise, the agent falls back to the first available model in the API list.

## Provider Comparison

| Feature | Claude (`claude`) | DeepSeek (`deepseek`) |
|---|---|---|
| **Auth Method** | Claude Code OAuth Token | Standard API Key |
| **Billing** | Claude Pro / Team Subscription | Pay-as-you-go API credits |
| **Default Model** | `claude-sonnet-4-6` | `deepseek-v4-flash` |
| **Model Override** | `CLAUDE_MODEL` / `LLM_MODEL` | `DEEPSEEK_MODEL` / `LLM_MODEL` |
| **Guardrails** | Refuses to run if `ANTHROPIC_API_KEY` is set | Standard |

## The `/model` Command

*(Note: The `/model` command functionality depends on PR #103 being merged).*

During an interactive session, you can view the current model or dynamically switch to a different model using the `/model` command.

```text
You: /model
Agent: Current model is claude-sonnet-4-6

You: /model claude-haiku-4-8
Agent: Switched to model claude-haiku-4-8
```

This dynamically overrides the provider's default model and the environment variables for the current session.
