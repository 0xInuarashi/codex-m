# codex-m

**Codex with independent routing for sub-agents and compaction.** This is a community fork of [openai/codex](https://github.com/openai/codex). It lets you keep your main agent on one model and speed while choosing a different model, reasoning effort, and speed for delegated work and context summarization.

The fork installs a separate `codex-m` command and shares your existing Codex authentication and ordinary configuration. Your existing `codex` installation stays available.

## What changes

- **Sub-agent routing:** configure a default model and reasoning effort, plus a service tier that can differ from the main agent's. Role-specific settings remain supported; upstream model/effort inheritance rules still apply to full-history forks.
- **Compaction routing:** choose the model, reasoning effort, and service tier used to summarize context without changing the main conversation's model.
- **Upstream sync:** a scheduled workflow merges `openai/codex/main` into the fork and publishes the merge only after the build and regression checks pass.
- **Local updates:** the launcher checks for newer fork revisions and can build, test, and install them with `codex-m update`.

## Install codex-m

The installation scripts currently support **Linux x86-64 with glibc**. Installation is from source; this repository does not currently provide a packaged codex-m installer for macOS, Windows, or ARM Linux.

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
git clone --branch codex-m/sol-ultrafast https://github.com/0xInuarashi/codex-m.git
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

There are two steps to an update:

1. **GitHub integrates upstream.** Every six hours, the [sync workflow](https://github.com/0xInuarashi/codex-m/actions/workflows/codex-m-sync.yml) checks upstream `main`, attempts a merge, refreshes the fork's workspace lockfile, and builds and tests the result. Conflicts or failing checks stop publication. The workflow can also be started manually from GitHub Actions.
2. **Your machine installs the updated fork.** When a newer fork revision is published, the launcher offers `Update now? [y/N]` on a subsequent interactive launch. Type `y` to build and install it; Enter continues with your current version.

You can check and update explicitly:

```bash
codex-m update --check
codex-m update
```

Automatic discovery runs in the background and caches results for up to six hours. `--check` refreshes the result immediately. The message **"OpenAI Codex has new changes awaiting integration into codex-m"** means upstream has advanced but a corresponding fork update has not been published yet; inspect the workflow's status before expecting an update prompt.

Local updates require a clean source checkout whose commits are included in the published fork. Commit and push your local changes, or reconcile divergent work, before updating. The updater builds in a separate worktree, runs tests, and switches the active installation only after staging all binaries and checking that the CLI starts. Settings and previous binaries are retained; running sessions keep their existing executables.

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
