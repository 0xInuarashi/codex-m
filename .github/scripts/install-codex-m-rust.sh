#!/usr/bin/env bash
# Install targets for the workspace toolchain, not the runner's default Rust.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../codex-rs"
toolchain=$(python3 - <<'PY'
import pathlib, tomllib
print(tomllib.loads(pathlib.Path('rust-toolchain.toml').read_text())['toolchain']['channel'])
PY
)
rustup toolchain install "$toolchain" --profile minimal --component clippy,rustfmt,rust-src
if (( $# )); then
  rustup target add --toolchain "$toolchain" "$@"
fi
rustc --version
# Exercise the toolchain Cargo will actually select before downloading/building dependencies.
probe_dir=$(mktemp -d)
trap 'rm -rf "$probe_dir"' EXIT
for target in "$@"; do
  printf 'pub fn target_probe() {}\n' | rustc --target "$target" --crate-name codex_m_target_probe \
    --crate-type lib --emit metadata -o "$probe_dir/probe.rmeta" -
done
