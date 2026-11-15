#!/usr/bin/env python3
"""Install real shared-session commands for the prebuilt Codex packages."""
import datetime
import os
from pathlib import Path
import shutil
import tempfile


def atomic_file(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install():
    home = Path.home()
    codex_home = Path(os.environ.get('CODEX_HOME', str(home / '.codex')))
    for package in ['codex-m', 'standalone']:
        binary = codex_home / 'packages' / package / 'current/bin/codex'
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise SystemExit(f'Install the {package} package first: missing {binary}')

    source = Path(__file__).resolve().parent
    config = home / '.config/codex-m'
    launcher = config / 'command'
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    backup = home / '.local/state/codex-m-commands' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    atomic_file(launcher, (source / 'codex-m-command').read_text(), 0o755)
    atomic_file(config / 'shell.bash', (source / 'codex-m-shell.bash').read_text(), 0o644)
    for name in ['codex', 'codex-m', 'codex-o']:
        command = bin_dir / name
        if command.is_symlink() and command.resolve() == launcher:
            continue
        if command.exists() or command.is_symlink():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(command, backup / name, follow_symlinks=False)
        temporary = bin_dir / f'.{name}-launcher-{os.getpid()}'
        try:
            temporary.symlink_to(launcher)
            os.replace(temporary, command)
        finally:
            temporary.unlink(missing_ok=True)

    # Source this after PATH edits so stale aliases/functions and command hashes
    # cannot hide the installed launchers in an existing Bash shell.
    bashrc = home / '.bashrc'
    content = bashrc.read_text() if bashrc.exists() else ''
    line = 'source "$HOME/.config/codex-m/shell.bash"'
    if line not in content.splitlines():
        content += '\n# Codex shared-session command launchers\n' + line + '\n'
        atomic_file(bashrc, content, bashrc.stat().st_mode & 0o777 if bashrc.exists() else 0o644)
    print('Installed codex and codex-m for the shared service; codex-o uses original Codex.')
    if backup.exists():
        print(f'Previous command entries preserved in {backup}')


if __name__ == '__main__':
    install()
