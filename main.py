"""Jurbas-Code — compatibility entrypoint.
This file redirects to jurbas_code.main.
"""

import sys
from jurbas_code import __version__
from jurbas_code.main import (
    main,
    load_history,
    save_history,
    HISTORY_FILE,
    SYSTEM_PROMPT,
    _is_dangerous,
    _is_readonly_bash,
    _requires_confirmation,
    confirm_action,
    run_bash,
    web_search,
)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        main(sys.argv[2:])
    else:
        main(sys.argv[1:])
