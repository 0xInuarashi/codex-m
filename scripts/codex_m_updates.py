"""Source-based updates for codex-m. No third-party Python dependencies."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

FORK = 'https://github.com/0xInuarashi/codex-m.git'
BRANCH = 'codex-m/sol-ultrafast'
UPSTREAM = 'https://github.com/openai/codex.git'
BINARIES = ('codex', 'codex-code-mode-host', 'codex-exec-server')


def run(*args, cwd=None, capture=False, timeout=None, env=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None,
                          timeout=timeout, env=env).stdout


def git(root, *args):
    return run('git', '-C', str(root), *args, capture=True).strip()


def install_home():
    return Path.home() / '.local/lib/codex-m'


def manifest():
    return json.loads((install_home() / 'current/installation.json').read_text())


def remote_head(url, branch):
    output = run('git', 'ls-remote', '--exit-code', url, f'refs/heads/{branch}',
                 capture=True, timeout=5)
    return output.split()[0]


def check(force=False):
    installed = manifest()
    cache = Path.home() / '.cache/codex-m/update-check.json'
    if not force:
        try:
            data = json.loads(cache.read_text())
            if data['installed'] == installed['commit'] and time.time() - data['checked'] < 21600:
                return data
        except (OSError, ValueError, KeyError):
            pass
    data = {'installed': installed['commit'], 'checked': time.time(),
            'fork': remote_head(FORK, BRANCH),
            'upstream': remote_head(UPSTREAM, 'main'),
            'installed_upstream': installed['upstream_commit']}
    cache.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(cache, json.dumps(data))
    return data


def describe(data):
    if data['fork'] != data['installed']:
        return 'codex-m update available. Run: codex-m update'
    if data['upstream'] != data['installed_upstream']:
        return ('OpenAI Codex has new changes awaiting integration into codex-m.\n'
                'Sync status: https://github.com/0xInuarashi/codex-m/actions/workflows/codex-m-sync.yml')
    return 'codex-m is up to date.'


def startup_check():
    installed = manifest()
    cache = Path.home() / '.cache/codex-m/update-check.json'
    try:
        data = json.loads(cache.read_text())
        if data['installed'] != installed['commit']:
            data = None
    except (OSError, ValueError, KeyError):
        data = None
    if data is None or time.time() - data['checked'] >= 21600:
        # Like upstream's TUI, discover updates for the next launch without delaying this one.
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--refresh-cache'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    return data


def startup_notice():
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return
    try:
        data = startup_check()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Offline startup must continue; the explicit command reports errors.
        if os.environ.get('CODEX_M_UPDATE_DEBUG'):
            print(f'codex-m update check: {error}', file=sys.stderr)
        return
    if data is None:
        return
    if data['fork'] != data['installed']:
        print(describe(data), file=sys.stderr)
        print('Update now? [y/N] ', end='', file=sys.stderr, flush=True)
        if input().strip().lower() in ('y', 'yes'):
            try:
                update()
            except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
                print(f'Update stopped: {error}. Continuing with the installed version.', file=sys.stderr)
    elif data['upstream'] != data['installed_upstream']:
        print(describe(data), file=sys.stderr)


def atomic_text(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextlib.contextmanager
def update_lock():
    root = install_home()
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'update.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def install(root, build_dir=None):
    """Stage all executables before one atomic switch; existing sessions retain old files."""
    root = Path(root).resolve()
    build_dir = Path(build_dir or root / 'codex-rs/target/dev-small')
    for name in BINARIES:
        if not (build_dir / name).is_file():
            raise RuntimeError(f'Missing built binary: {build_dir / name}')
    commit = git(root, 'rev-parse', 'HEAD')
    upstream = git(root, 'merge-base', 'HEAD', 'refs/remotes/upstream/main')
    base = install_home()
    release = base / 'releases' / f'{commit[:12]}-{uuid.uuid4().hex[:8]}'
    release.mkdir(parents=True)
    try:
        for name in BINARIES:
            shutil.copy2(build_dir / name, release / name)
        shutil.copy2(root / 'scripts/codex_m_updates.py', release / 'codex_m_updates.py')
        (release / 'installation.json').write_text(json.dumps({
            'commit': commit, 'upstream_commit': upstream, 'source': str(root),
            'target_dir': str(build_dir.resolve().parent),
        }, indent=2) + '\n')
        # Verify the staged CLI can start before changing the active installation.
        run(str(release / 'codex'), '--version', capture=True, timeout=15)
        defaults = Path.home() / '.config/codex-m/config.toml'
        if not defaults.exists():
            atomic_text(defaults, (root / 'scripts/codex-m.defaults.toml').read_text())
        atomic_text(Path.home() / '.local/bin/codex-m', (root / 'scripts/codex-m').read_text(), 0o755)
        temporary = base / f'.current-{uuid.uuid4().hex}'
        temporary.symlink_to(release.relative_to(base))
        os.replace(temporary, base / 'current')
    except BaseException:
        shutil.rmtree(release)
        raise
    print(f'Installed codex-m {commit[:12]}. Previous binaries were retained.')


def prepare(root, url=FORK, branch=BRANCH):
    """Fetch the exact fork branch and refuse divergence; never alter the source worktree."""
    if git(root, 'status', '--porcelain'):
        raise RuntimeError(f'Commit or stash local changes in {root} before updating.')
    args = ['fetch', '--no-tags']
    if git(root, 'rev-parse', '--is-shallow-repository') == 'true':
        args.append('--unshallow')
    git(root, *args, url, f'refs/heads/{branch}')
    target = git(root, 'rev-parse', 'FETCH_HEAD')
    try:
        git(root, 'merge-base', '--is-ancestor', 'HEAD', target)
    except subprocess.CalledProcessError as error:
        raise RuntimeError('Local source has commits absent from the published fork; reconcile and push them before updating.') from error
    # Record the upstream baseline in the new installation, including after a sync merge.
    git(root, 'fetch', '--no-tags', UPSTREAM, 'refs/heads/main:refs/remotes/upstream/main')
    directory = Path.home() / '.cache/codex-m/worktrees' / f'{target[:12]}-{uuid.uuid4().hex[:8]}'
    directory.parent.mkdir(parents=True, exist_ok=True)
    git(root, 'worktree', 'add', '--detach', str(directory), target)
    return directory


def update():
    with update_lock():
        installed = manifest()
        root = Path(installed['source'])
        directory = prepare(root)
        print(f'Building update in {directory}; installed binaries remain active.', flush=True)
        # Reuse one target directory across updates; source always stays isolated.
        env = dict(os.environ)
        env['CARGO_TARGET_DIR'] = installed.get('target_dir', str(Path.home() / '.cache/codex-m/target'))
        run(sys.executable, str(directory / 'scripts/build-codex-m.py'), '--test', env=env)
        install(directory, Path(env['CARGO_TARGET_DIR']) / 'dev-small')


def main():
    parser = argparse.ArgumentParser(description='Check or install tested codex-m source updates.')
    parser.add_argument('--refresh-cache', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--check', action='store_true', help='Check upstream and fork without installing')
    parser.add_argument('--install-source', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.install_source:
            with update_lock():
                target = os.environ.get('CARGO_TARGET_DIR')
                install(args.install_source, Path(target) / 'dev-small' if target else None)
        elif args.refresh_cache:
            cache_dir = Path.home() / '.cache/codex-m'
            cache_dir.mkdir(parents=True, exist_ok=True)
            with (cache_dir / 'refresh.lock').open('w') as refresh:
                try:
                    fcntl.flock(refresh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return 0
                check()
        elif args.check:
            print(describe(check(force=True)))
        else:
            update()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'codex-m update stopped: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
