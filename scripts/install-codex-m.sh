#!/usr/bin/env bash
set -euo pipefail
codex_m_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$codex_m_root/scripts/codex_m_updates.py" --install-source "$codex_m_root"
