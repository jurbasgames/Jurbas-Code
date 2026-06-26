import jurbas_code

def cmd_help(agent, args):
    """List available commands and their descriptions."""
    lines = ["Available commands:"]
    for name, handler in COMMAND_HANDLERS.items():
        desc = handler.__doc__ or "No description available."
        lines.append(f"  {name} - {desc}")
    return "\n".join(lines)

def cmd_status(agent, args):
    """Show current provider, model, and session stats."""
    model = "unknown"
    try:
        from jurbas_code.providers import resolve_provider_model
        model = resolve_provider_model(agent.provider, agent.client)
    except Exception:
        pass

    lines = [
        "Session Status:",
        f"  Provider: {agent.provider}",
        f"  Model: {model}",
        f"  Tokens: {agent.session_tokens['prompt']} prompt / {agent.session_tokens['completion']} completion / {agent.session_tokens['total']} total"
    ]
    return "\n".join(lines)

def cmd_clear(agent, args):
    """Clear the conversation history (keeps system prompt)."""
    if not agent.messages:
        return "History already clear."

    system_prompt = None
    if agent.messages and agent.messages[0].get("role") == "system":
        system_prompt = agent.messages[0]

    agent.messages = []
    if system_prompt:
        agent.messages.append(system_prompt)

    return "Conversation history cleared."

def cmd_version(agent, args):
    """Print the current Jurbas-Code version."""
    from jurbas_code import __version__
    return f"Jurbas-Code version: {__version__}"

COMMAND_HANDLERS = {
    "/help": cmd_help,
    "/status": cmd_status,
    "/clear": cmd_clear,
    "/version": cmd_version,
}

def handle_command(agent, user_input: str) -> str:
    """Parse and execute a slash command."""
    parts = user_input.strip().split(" ", 1)
    command_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handler = COMMAND_HANDLERS.get(command_name)
    if handler:
        return handler(agent, args)

    return f"Unknown command: {command_name}"
