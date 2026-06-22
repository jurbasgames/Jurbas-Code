"""Backward compatibility layer for tools."""

import os
import shutil
import subprocess

from jurbas_code.tools import (
    BASH_TIMEOUT,
    safe_path,
    is_secret_path,
    load_dotenv,
    _is_dangerous,
    _is_readonly_bash,
    _requires_confirmation,
    confirm_action,
    read_file,
    list_directory,
    write_file,
    run_bash,
    web_search,
    TOOL_HANDLERS,
)

from jurbas.config import tools

try:
    from duckduckgo_search import DDGS
    HAS_WEB_SEARCH = True
except ImportError:
    HAS_WEB_SEARCH = False
