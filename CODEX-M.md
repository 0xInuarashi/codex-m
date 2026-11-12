# codex-m local fork

The upstream `codex` installation is unchanged. This fork supports optional routing
settings in a normal config layer (including `-c` overrides):

```toml
[agents]
default_subagent_model = "gpt-6.1-sol"
default_subagent_reasoning_effort = "medium"

[model_routing]
subagent_service_tier = "ultrafast"
compaction_model = "gpt-6.1-sol"
compaction_service_tier = "ultrafast"
```

All routing values are optional. Omitting them preserves upstream behavior.
Sub-agent speed no longer follows the root when `subagent_service_tier` is set.
Unsupported model tiers remain subject to the upstream capability filter.
Model and reasoning defaults and custom role-specific model/effort settings use
upstream precedence. Explicit role model/effort settings remain available.

The compaction overrides apply to local summarization and foreground/background
remote V2 compaction requests. They do not change the foreground model. The token
budget rollover feature does not request model summarization and is unchanged.
Cross-model encrypted compaction must be tested against the serving backend.

Build:

```sh
python3 /repos/codex-m/scripts/build-codex-m.py
```

This fork is published at https://github.com/0xInuarashi/codex-m and is based on
https://github.com/openai/codex.

## Launcher and settings

`codex-m` loads `~/.config/codex-m/config.toml` on top of the ordinary Codex config.
Explicit `-c` flags passed to the launcher override these defaults. The upstream
`codex` binary does not read this file. Launched from your home directory, the
launcher starts in `/repos`; launched elsewhere, it preserves that directory.

Compaction also accepts `model_routing.compaction_reasoning_effort`. Sub-agent
model and effort use the existing `agents.default_subagent_model` and
`agents.default_subagent_reasoning_effort`. Per-task spawn model/effort overrides
remain supported. Custom agent role files can set `model`,
`model_reasoning_effort`, and `service_tier`; in independent routing mode an
explicit role tier overrides `model_routing.subagent_service_tier`.

A running upstream session continues to use the upstream binary. Resume it with
`codex-m resume` to run subsequent turns on the fork. This installation does not
replace or restart the existing app-server daemon.

Install the three built binaries and launcher with
`/repos/codex-m/scripts/install-codex-m.sh`. Existing codex-m settings are preserved.
The build uses Codex's own V8 release artifacts, verified against the checksums
committed in `third_party/v8`. It does not require building V8 from source.

## Local validation

The live routing check used an Astra Fast parent and Sol Ultrafast children at low,
high, and configured-default medium effort. The installed launcher also executed
a shell command successfully. The comparison harness uses three synthetic
handoffs, 18 scored facts each, plus a later message exceeding the 64,000-token
retention budget. Every condition (no compaction, Astra Fast compaction, Sol
Ultrafast compaction) recalled 54/54 items. Mean compaction wall time was 33.7s for
Astra and 10.4s for Sol. This small synthetic benchmark does not establish general
quality equivalence. Local results are in
`validation/compaction-benchmark-final/summary.json`.

Targeted Rust tests on this host require a larger test-thread stack:

```sh
cd /repos/codex-m/codex-rs
RUST_MIN_STACK=33554432 cargo test -p codex-core --lib --profile dev-small independent_service_tier
RUST_MIN_STACK=33554432 cargo test -p codex-core --lib --profile dev-small compact::tests
```
