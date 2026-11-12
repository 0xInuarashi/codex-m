#!/usr/bin/env python3
"""Exercise the release packaging command before an expensive Rust build."""
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import tomllib

root = Path(os.environ['CODEX_REPO_ROOT']).resolve()
target = 'x86_64-unknown-linux-musl'
with tempfile.TemporaryDirectory(prefix='codex-m-package-check-') as directory:
    temp = Path(directory)
    binaries = temp / 'bin'
    binaries.mkdir()
    for name in ('codex', 'codex-code-mode-host', 'codex-exec-server', 'bwrap', 'rg'):
        path = binaries / name
        path.write_text('#!/bin/sh\nexit 0\n')
        path.chmod(0o755)
    # All binaries must be supplied; packaging must not silently rebuild one.
    cargo = binaries / 'cargo'
    cargo.write_text('#!/bin/sh\necho "Unexpected Cargo invocation during packaging" >&2\nexit 99\n')
    cargo.chmod(0o755)
    env = dict(os.environ, RUNNER_TEMP=str(temp), PATH=f'{binaries}:{os.environ["PATH"]}')
    subprocess.run([
        'bash', str(root / '.github/scripts/build-codex-package-archive.sh'),
        '--target', target, '--bundle', 'primary',
        '--entrypoint-dir', str(binaries), '--archive-dir', str(temp / 'dist'),
        '--rg-bin', str(binaries / 'rg'),
    ], env=env, cwd=root, check=True)
    archive = temp / 'dist' / f'codex-package-{target}.tar.gz'
    with tarfile.open(archive) as package:
        required = {'bin/codex', 'bin/codex-code-mode-host', 'bin/codex-exec-server',
                    'codex-resources/bwrap', 'codex-path/rg', 'codex-package.json'}
        assert required.issubset(package.getnames())
        metadata = json.load(package.extractfile('codex-package.json'))
        version = tomllib.loads((root / 'codex-rs/Cargo.toml').read_text())['workspace']['package']['version']
        assert metadata['version'] == version
        assert metadata['target'] == target
print('Release packaging preflight passed')
