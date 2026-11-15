# codex-m

**Codex with independent routing for sub-agents and compaction.** This is a community fork of [openai/codex](https://github.com/openai/codex). It lets you keep your main agent on one model and speed while choosing a different model, reasoning effort, and speed for delegated work and context summarization.

The fork installs a separate `codex-m` command and shares your existing Codex authentication and ordinary configuration. Your existing `codex` installation stays available.

## Branches

**`main` is the canonical codex-m branch.** Clone and install from it. The `upstream` remote points to OpenAI's repository; `upstream/main` tracks its original code. The sync workflow merges upstream changes into our `main` while preserving the fork's changes.

`codex-m/sol-ultrafast` is retained as a migration branch for older installed updaters. Updating once through that branch switches future checks to `main`. `upstream-snapshot` preserves the previous upstream-only branch as a historical snapshot.

## What changes

- **Sub-agent routing:** configure a default model and reasoning effort, plus a service tier that can differ from the main agent's. Role-specific settings remain supported; upstream model/effort inheritance rules still apply to full-history forks.
- **Compaction routing:** choose the model, reasoning effort, and service tier used to summarize context without changing the main conversation's model.
- **Upstream sync:** a scheduled workflow merges `openai/codex/main` into the fork and publishes the merge only after the build and regression checks pass.
- **Binary updates:** the native update prompt installs published fork releases without compiling locally.

## Install codex-m

Prebuilt releases target **Linux x86-64**, using upstream's **musl** toolchain and standalone package layout. They do not require Python, Rust, Git, a recent glibc, or a system OpenSSL installation. Other platforms are not yet published by this fork.

```bash
curl -fsSL https://raw.githubusercontent.com/0xInuarashi/codex-m/main/install.sh | sh
```

The installer verifies release checksums, installs `~/.local/bin/codex-m`, and stores packages under `${CODEX_HOME:-~/.codex}/packages/codex-m`. Existing Codex authentication and fork settings are preserved. Once installed, run `codex-m login` if needed, then `codex-m`.

Published binaries are listed in [Releases](https://github.com/0xInuarashi/codex-m/releases). Build and verification status is available in [Actions](https://github.com/0xInuarashi/codex-m/actions/workflows/codex-m-release.yml).

### Optional: build from source

The following developer installation uses the older Python source-build updater. Python and Rust are build requirements for this route, not requirements of the prebuilt installer.

### 1. Install prerequisites

You need Git, Python **3.11 or newer**, and Rust installed through [rustup](https://rustup.rs/). The repository's [toolchain file](codex-rs/rust-toolchain.toml) selects the Rust version used for the build. Allow several minutes or longer for compilation and tens of gigabytes of free disk space for dependencies and build output.

On Ubuntu 24.04, install the native build dependencies with:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  git python3 build-essential pkg-config libssl-dev libcap-dev \
  libasound2-dev bubblewrap clang cmake protobuf-compiler
```

Install rustup separately if it is not already available, then make sure Cargo is on your shell's path:

```bash
source "$HOME/.cargo/env"
```

### 2. Clone the fork and configure upstream

```bash
git clone --branch main https://github.com/0xInuarashi/codex-m.git
cd codex-m

git remote add upstream https://github.com/openai/codex.git
git fetch --no-tags upstream main
```

The installer uses `upstream/main` to record which upstream revision your build contains. Keep the source checkout: the updater uses it to prepare future builds.

### 3. Build, test, and install

Run these commands from the repository root:

```bash
CARGO_BUILD_JOBS=2 python3 scripts/build-codex-m.py --test
scripts/install-codex-m.sh

export PATH="$HOME/.local/bin:$PATH"
codex-m --version
```

The build script downloads checksum-verified V8 artifacts from upstream, builds the CLI and its two helper executables, and runs the fork's regression tests. You can raise `CARGO_BUILD_JOBS` on machines with more memory.

Add `export PATH="$HOME/.local/bin:$PATH"` to your shell startup file, such as `~/.bashrc`, if that directory is not already on your persistent path.

The installer creates:

| Location | Purpose |
| --- | --- |
| `~/.local/bin/codex-m` | Launcher and update command |
| `~/.local/lib/codex-m/releases/` | Installed binaries, including retained previous versions |
| `~/.local/lib/codex-m/current` | Pointer to the active installation |
| `~/.config/codex-m/config.toml` | Fork-specific routing defaults |

### 4. Start using it

```bash
cd /path/to/your/project
codex-m
```

If you have not signed in to Codex on this machine, run `codex-m login`. To continue an existing session using the fork, run:

```bash
codex-m resume
```

Existing sessions and app-server daemons continue using the binary they started with. Launch or resume through `codex-m` to use the fork.

### Share terminal sessions with mobile

Terminal and mobile clients must use the same app server to share a running conversation. A plain `codex-m` launch can run an independent embedded server because the fork's routing defaults are loaded as configuration overrides. Two independent servers cannot own the same conversation: the second reports an active writer conflict.

With a codex-m app server already running on the default local socket, connect explicitly:

```bash
codex-m --remote unix:// resume SESSION_ID
```

Exit any independent terminal session holding that conversation before resuming it through the shared server. Closing a terminal attached to the shared server leaves the server running.

For prebuilt installations, the optional [command installer](scripts/install-codex-m-commands.py) creates real `codex`, `codex-m`, and `codex-o` executables in `~/.local/bin`. Interactive `codex` and `codex-m` launches, including `resume`, `fork`, and `agents`, use `--remote unix://` automatically. `codex-o` executes the original standalone package independently with `--no-daemon`. **All three add `--yolo`, which disables sandboxing and approval prompts.** With both prebuilt packages installed, opt in from the repository root:

```bash
python3 scripts/install-codex-m-commands.py
source ~/.bashrc
which codex codex-m codex-o
```

The installer preserves the previous command entries in `~/.local/state/codex-m-commands`, leaves package binaries intact, and adds a Bash startup hook that clears old aliases, functions, and cached command paths. The commands work without alias expansion, including in scripts and other shells with `~/.local/bin` on `PATH`. Maintenance and non-interactive commands retain their normal connection behavior. Explicit `--remote` addresses are respected; use `codex-m --no-daemon` for an independent local session.

The codex-m installer and native updater preserve these shared-session launchers. Rerunning the command installer is safe if another package installer replaces the visible command links. Already-running independent sessions retain their conversation locks until they exit; installing launchers does not transfer or terminate them.

The launchers connect to an existing service; they do not install or start one. The service must run the fork binary, for example `codex-m app-server --remote-control --listen unix://`. The upstream daemon manager may select its separately installed standard Codex package even when invoked through `codex-m remote-control start`.

## Configure routing

Edit `~/.config/codex-m/config.toml`. A fresh installation writes these defaults:

```toml
service_tier = "fast"

[agents]
default_subagent_model = "gpt-6.1-sol"
default_subagent_reasoning_effort = "medium"

[model_routing]
subagent_service_tier = "ultrafast"
compaction_model = "gpt-6.1-sol"
compaction_service_tier = "ultrafast"
compaction_reasoning_effort = "medium"
```

Choose model names and service tiers available to your account. The defaults do not grant access to additional models or tiers, and unsupported tiers remain subject to upstream capability filtering. The `fast` alias resolves to `priority`.

These settings layer on top of your ordinary Codex configuration. Explicit `-c` arguments override the fork defaults, for example:

```bash
codex-m -c 'model_routing.compaction_reasoning_effort="low"'
```

The installer preserves an existing codex-m configuration. Remove optional routing settings to use upstream behavior for those settings. See [CODEX-M.md](CODEX-M.md) for inheritance rules, compaction details, and validation notes.

## Update codex-m

The [sync workflow](https://github.com/0xInuarashi/codex-m/actions/workflows/codex-m-sync.yml) merges upstream main and the latest stable release every six hours, advances the fork's base version to that release, and publishes only after its build and regression checks pass. Release-specific fixes are included even when upstream main has not changed. Workspace-version conflicts are resolved automatically; source conflicts or failing checks stop integration.

Changes on `main` trigger the [release workflow](https://github.com/0xInuarashi/codex-m/actions/workflows/codex-m-release.yml). Once a binary release is published, the native Codex update dialog offers it on startup. Update discovery is cached, so a new release may not appear immediately. An upstream commit alone is not an installable update.

Publishing a release does not install it on your machine or restart a running remote-control service. After installing an update, restart that service to use the new binary; existing processes keep their previous version until restarted.

To install the latest binary release immediately, rerun the curl installer above. Existing source installations can migrate with the same command. The older Python launcher still supports `codex-m update` for source builds; the native binary uses the startup dialog and installer instead.

To disable automatic checks, add this **top-level** setting before any table headers in `~/.config/codex-m/config.toml`:

```toml
check_for_update_on_startup = false
```

## Documentation and license

- [Fork implementation and validation notes](CODEX-M.md)
- [Build script](scripts/build-codex-m.py) and [installer](scripts/install-codex-m.sh)
- [Upstream Codex documentation](https://developers.openai.com/codex)
- [Upstream repository](https://github.com/openai/codex)

Licensed under [Apache-2.0](LICENSE). See [NOTICE](NOTICE) for attribution.
