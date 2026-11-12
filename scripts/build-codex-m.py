#!/usr/bin/env python3
"""Build the fork with checksum-verified Codex V8 release artifacts."""
import argparse
import concurrent.futures
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--test', action='store_true', help='Run routing and compaction regression tests after building')
args = parser.parse_args()
root=Path(__file__).resolve().parents[1]
lock=tomllib.loads((root/'codex-rs/Cargo.lock').read_text())
version=next(p['version'] for p in lock['package'] if p['name']=='v8')
target='x86_64-unknown-linux-gnu'
names=[f'librusty_v8_ptrcomp_sandbox_release_{target}.a.gz',f'src_binding_ptrcomp_sandbox_release_{target}.rs']
checksums=dict(line.split(maxsplit=1)[::-1] for line in (root/f'third_party/v8/rusty_v8_{version.replace(".","_")}.sha256').read_text().splitlines())
dest=root/'build-support/v8';dest.mkdir(parents=True,exist_ok=True)
def fetch(name):
    path=dest/name
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=checksums[name]:
        data=urllib.request.urlopen(f'https://github.com/openai/codex/releases/download/rusty-v8-v{version}/{name}',timeout=120).read()
        if hashlib.sha256(data).hexdigest()!=checksums[name]:raise RuntimeError(f'Checksum mismatch: {name}')
        path.write_bytes(data)
    return str(path)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:archive,binding=list(pool.map(fetch,names))
env=dict(os.environ,RUSTY_V8_ARCHIVE=archive,RUSTY_V8_SRC_BINDING_PATH=binding)
env.setdefault('CARGO_BUILD_JOBS','8')
cargo=Path.home()/'.cargo/bin/cargo'
if not cargo.exists():cargo=shutil.which('cargo')
subprocess.run([str(cargo),'build','--locked','--profile','dev-small','-p','codex-cli','-p','codex-code-mode-host','-p','codex-exec-server-cli','--bins'],cwd=root/'codex-rs',env=env,check=True)

if args.test:
    env.setdefault('RUST_MIN_STACK', '33554432')
    for package, filters in (
        ('codex-config', ['model_routing']),
        ('codex-install-context', ['fork_package_layout']),
        ('codex-tui', ['update_versions::', 'update_action::', 'updates_cache::', 'update_prompt::']),
        ('codex-core', ['independent_service_tier', 'agent::role::tests', 'compact::tests', 'compact_remote_v2::', 'compaction_routing']),
    ):
        for test_filter in filters:
            subprocess.run([str(cargo), 'test', '--locked', '--profile', 'dev-small', '-p', package,
                            '--lib', test_filter], cwd=root/'codex-rs', env=env, check=True)
    subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', str(root/'scripts'),
                    '-p', 'test_codex_m_updates.py'], cwd=root, check=True)

    subprocess.run([str(cargo), 'test', '--locked', '--profile', 'dev-small', '-p', 'codex-cli',
                    '--bin', 'codex', 'codex_m::'], cwd=root/'codex-rs', env=env, check=True)
    subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', str(root/'scripts'),
                    '-p', 'test_codex_m_installer.py'], cwd=root, check=True)
