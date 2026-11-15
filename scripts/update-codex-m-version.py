#!/usr/bin/env python3
"""Track stable upstream versions and resolve only workspace-version conflicts."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib

MANIFEST = 'codex-rs/Cargo.toml'
VERSION_LINE = re.compile(r'(\[workspace\.package\]\s*\nversion\s*=\s*)"[^"]+"')


def replace_version(source, version):
    updated, count = VERSION_LINE.subn(lambda match: match[1] + f'"{version}"', source)
    if count != 1:
        raise ValueError('Expected exactly one workspace package version')
    return updated


def fork_version(tag, current):
    match = re.fullmatch(r'rust-v(\d+\.\d+\.\d+)', tag)
    if not match:
        raise ValueError(f'Expected a stable upstream release tag, got {tag!r}')
    version = match[1]
    if tuple(map(int, version.split('.'))) < tuple(map(int, current.split('-')[0].split('.'))):
        raise ValueError(f'Refusing to downgrade {current} to {version}')
    return version + '-codex-m.1'


def update(tag, resolve_merge=False):
    path = Path(MANIFEST)
    if resolve_merge:
        conflicts = subprocess.check_output(
            ['git', 'diff', '--name-only', '--diff-filter=U'], text=True).splitlines()
        if MANIFEST not in conflicts:
            return
        sources = [subprocess.check_output(['git', 'show', f':{stage}:{MANIFEST}'], text=True)
                   for stage in (2, 1, 3)]  # ours, base, theirs
        current = tomllib.loads(sources[0])['workspace']['package']['version']
        version = fork_version(tag, current)
        with tempfile.TemporaryDirectory(prefix='codex-m-version-merge-') as directory:
            files = []
            for index, source in enumerate(sources):
                file = Path(directory) / str(index)
                file.write_text(replace_version(source, version))
                files.append(str(file))
            result = subprocess.run(['git', 'merge-file', '-p', *files], capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Cargo.toml has conflicts beyond its workspace version; resolve manually')
        path.write_text(result.stdout)
        subprocess.run(['git', 'add', MANIFEST], check=True)
    else:
        source = path.read_text()
        current = tomllib.loads(source)['workspace']['package']['version']
        path.write_text(replace_version(source, fork_version(tag, current)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_tag')
    parser.add_argument('--resolve-merge', action='store_true')
    args = parser.parse_args()
    update(args.release_tag, args.resolve_merge)
