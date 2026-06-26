# Project: Jurbas-Code Branch Integration

## Architecture
- `main.py`: Entrypoint for the application.
- `tests/`: Directory containing pytest unit and integration tests.
- Code layout comprises modularization packages under extraction.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Foundation Integrations | Merge `split/error-handling`, `split/env-secrets`, `split/modular-package` | None | DONE |
| 2 | Features & OS Support | Merge `feat/add-help-flag-17262696986930256488`, `feature/session-history-4383249331170608718`, `web-search-tool`, `fix/windows-cross-platform-support`, `fix-run-bash-windows-encoding-crash-7830832139091028528` | M1 | DONE |
| 3 | Architecture Modularization | Merge `extract-providers-phase-3-17939500207056494351`, `extract-agent-loop-7138581612168314532`, `architecture-phase-2-extract-tools-5122756231442905008`, `arch-phase-6-modularization-3129979530355619415` | M2 | DONE |

## Interface Contracts
- All merged modules must compile successfully with `python -m py_compile main.py` (and any new modules).
- Public APIs, environment secrets format, and error handling behaviors must maintain compatibility with existing tests.
