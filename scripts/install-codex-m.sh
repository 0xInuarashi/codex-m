#!/usr/bin/env bash
set -euo pipefail
codex_m_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
install -d "$HOME/.local/lib/codex-m" "$HOME/.local/bin" "$HOME/.config/codex-m"
for codex_m_binary in codex codex-code-mode-host codex-exec-server; do
    install -m 755 "$codex_m_root/codex-rs/target/dev-small/$codex_m_binary" "$HOME/.local/lib/codex-m/$codex_m_binary"
done
install -m 755 "$codex_m_root/scripts/codex-m" "$HOME/.local/bin/codex-m"
if [[ ! -e "$HOME/.config/codex-m/config.toml" ]]; then
    install -m 644 "$codex_m_root/scripts/codex-m.defaults.toml" "$HOME/.config/codex-m/config.toml"
fi
