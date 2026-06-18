# Jurbas-Code

## 2. 🔧 Expandir o conjunto de ferramentas

Hoje o agente só **lê** arquivos. Ferramentas naturais para adicionar:

| Ferramenta | Descrição |
|---|---|
| `write_file` | Criar/editar arquivos |
| `list_directory` | Navegar pelo sistema de arquivos |
| `search_in_files` (grep) | Buscar padrões dentro de arquivos |
| `execute_command` | Rodar comandos shell (com cuidado!) |
| `web_search` | Buscar na internet |

---

## 3. 📜 Suporte a streaming

Hoje a resposta aparece de uma vez. Com streaming, o texto aparece token a token, melhorando a experiência:

```python
response = client.chat.completions.create(..., stream=True)
for chunk in response:
    ...
```

---

## 4. 🪵 Sistema de logging e persistência

- Substituir `print` por logging com níveis (DEBUG, INFO, ERROR).
- Salvar o histórico da conversa em arquivo (ex: `history.json`) para continuar entre sessões.
- Lidar com **limite de tokens**: truncar ou sumarizar mensagens antigas.

---

## 5. 🔁 Múltiplas tool calls em sequência

Hoje o código processa tool calls apenas uma vez. O ideal é um loop que continue processando enquanto o modelo pedir novas ferramentas, possibilitando fluxos como: *listar diretório → ler arquivo → editar arquivo*.

---

## 6. ⚙️ Arquivo de configuração

Externalizar API key, modelo, system prompt e parâmetros para um `.env` + `config.yaml`:

```yaml
model: "deepseek-v4-pro"
reasoning_effort: "high"
tools_enabled: ["read_file", "write_file", "list_directory"]
```

---

## 7. 🛡️ Segurança e sandboxing

- Confirmar operações destrutivas (antes de escrever/deletar arquivos).
- Limitar diretórios acessíveis.
- Sandbox para comandos shell (Docker, timeout, etc.).

---

## 8. 🧩 Modo não-interativo

Permitir receber um prompt diretamente da linha de comando:

```bash
python main.py "Explique o arquivo ./src/utils.py"
```

---

## Running tests

Run tests via uv:
```bash
uv run pytest
```
