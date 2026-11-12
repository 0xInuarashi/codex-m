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
python3 scripts/build-codex-m.py --test
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
`scripts/install-codex-m.sh`. Existing codex-m settings are preserved.
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

## Keeping the fork up to date

The `Sync codex-m with upstream` GitHub Actions workflow checks `openai/codex/main`
every six hours and can also be run manually. It merges upstream into an isolated
runner checkout of `codex-m/sol-ultrafast`, refreshes workspace entries in the lockfile
for the fork's package version, builds the three executables, and runs
routing, compaction, and updater regression tests. Only a successful merge and
validation are pushed. Conflicts, failed checks, or a concurrent push stop the run;
the published fork is unchanged. Inspect failed runs in the repository's Actions
tab. GitHub may disable scheduled workflows in an inactive public repository.
The publish step uses the repository-specific `codex-m upstream sync` write deploy
key, stored in the `CODEX_M_SYNC_SSH_KEY` Actions secret. This lets upstream
workflow-file changes travel with the merge. No personal access token is stored
in Actions; revoke the deploy key or remove the secret to disable automated pushes.

The local launcher checks for updates on interactive startup (including `resume`
and `fork`), at most once every six hours. Discovery runs in the background;
a newly discovered update is offered on the next launch. It distinguishes a newer fork commit
from upstream work that still needs integration. Offline checks do not prevent
startup. `check_for_update_on_startup = false` in the normal Codex config or the
codex-m config disables these automatic checks. Noninteractive invocations do not
print notices or contact GitHub for update discovery.

```sh
codex-m update --check  # force a read-only version check
codex-m update          # fetch, build, test, and install the fork
```

An update requires a clean source checkout and a fast-forward relationship to the
published fork. Local uncommitted work or divergent commits must be reconciled
first. The updater builds in a separate Git worktree under `~/.cache/codex-m/`,
runs the regression checks, and stages all binaries before atomically switching
`~/.local/lib/codex-m/current`. Existing sessions keep running their original
executables. Previous binary directories are retained in `releases/`; settings
are preserved. Updates never install the official package over the fork and do
not restart the app-server daemon.

This source installer currently targets Linux x86-64, requires Python 3.11+, Git,
the Rust toolchain in `codex-rs/rust-toolchain.toml`, native build dependencies,
and substantial free disk space. Builds can take several minutes. The automated
checks cover the fork's changed behavior; they do not establish full upstream
behavioral compatibility or backend acceptance of every cross-model compaction.
