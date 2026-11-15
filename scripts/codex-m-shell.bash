# Remove the old alias-only setup and use the installed command launchers.
unalias codex codex-m codex-o 2>/dev/null || true
unset -f codex codex-m codex-o 2>/dev/null || true
export PATH="$HOME/.local/bin:$PATH"
hash -r
