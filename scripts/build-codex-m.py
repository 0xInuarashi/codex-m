#!/usr/bin/env python3
"""Build the fork with checksum-verified Codex V8 release artifacts."""
import concurrent.futures
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
import urllib.request

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
subprocess.run([str(cargo),'build','--profile','dev-small','-p','codex-cli','-p','codex-code-mode-host','-p','codex-exec-server-cli','--bins'],cwd=root/'codex-rs',env=env,check=True)
