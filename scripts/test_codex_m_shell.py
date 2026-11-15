"""Exercise installed commands without starting real Codex sessions."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


INSTALLER = Path(__file__).with_name('install-codex-m-commands.py')


@unittest.skipUnless(shutil.which('bash'), 'Bash is required')
class ShellDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='codex-m-shell-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.bin = self.home / '.local/bin'
        self.bin.mkdir(parents=True)
        self.env = {**os.environ, 'HOME': str(self.home),
                    'CODEX_HOME': str(self.home / '.codex'),
                    'PATH': f'{self.bin}:/usr/bin:/bin'}
        stub = self.home / '.codex/packages/codex-m/current/bin/codex'
        stub.parent.mkdir(parents=True)
        stub.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\nexit "${CODEX_M_TEST_EXIT:-0}"\n')
        stub.chmod(0o755)
        original = self.home / '.codex/packages/standalone/current/bin/codex'
        original.parent.mkdir(parents=True)
        original.write_text('#!/bin/bash\nprintf "%s\\0" original "$@"\n')
        original.chmod(0o755)
        (self.bin / 'codex-m').symlink_to(stub)
        (self.bin / 'codex').symlink_to(original)
        self.install()

    def install(self):
        subprocess.run([sys.executable, str(INSTALLER)], env=self.env,
                       capture_output=True, text=True, check=True)

    def run_helper(self, arguments, *, exit_code=0, reload=False, command='codex-m'):
        invocation = [str(self.bin / command), *arguments]
        if reload:
            source = ('shopt -s expand_aliases\n'
                      'alias codex-m="codex-m --yolo"\n'
                      'alias codex="codex-m --yolo"\n'
                      'alias codex-o="command codex --yolo"\n'
                      'source "$HOME/.bashrc"\nsource "$HOME/.bashrc"\n'
                      + command + ' "$@"')
            invocation = ['bash', '--noprofile', '--norc', '-c', source, 'shell-test', *arguments]
        result = subprocess.run(
            invocation,
            env={**self.env, 'CODEX_M_TEST_EXIT': str(exit_code)},
            capture_output=True,
        )
        self.assertEqual(result.returncode, exit_code, result.stderr.decode())
        self.assertEqual(result.stderr, b'')
        return [arg.decode() for arg in result.stdout.removesuffix(b'\0').split(b'\0')]

    def test_interactive_commands_use_shared_service(self):
        for args in [[], ['resume'], ['resume', 'thread-id'], ['resume', '--last'],
                     ['fork', 'thread-id'], ['agents'], ['please fix this']]:
            with self.subTest(args=args):
                self.assertEqual(self.run_helper(args), ['--yolo', '--remote', 'unix://', *args])

    def test_maintenance_and_noninteractive_commands_keep_their_own_routing(self):
        for command in ['exec', 'e', 'review', 'login', 'logout', 'mcp', 'plugin',
                        'app-server', 'remote-control', 'completion', 'update', 'doctor',
                        'sandbox', 'debug', 'apply', 'a', 'queue', 'archive', 'delete',
                        'migrate-rollouts', 'migrate-nfs-db', 'unarchive', 'cloud',
                        'cloud-tasks', 'exec-server', 'features', 'help', 'app',
                        'tcp-tunnel', 'git-credential', 'execpolicy', 'responses-api-proxy',
                        'stdio-to-uds']:
            with self.subTest(command=command):
                args = [command, '--help']
                self.assertEqual(self.run_helper(args), ['--yolo', *args])

    def test_option_values_are_not_mistaken_for_commands(self):
        for option in ['-c', '--config', '-m', '--model', '-i', '--image', '-p', '--profile',
                       '-s', '--sandbox', '-C', '--cd', '-a', '--ask-for-approval',
                       '--enable', '--disable', '--local-provider', '--remote-auth-token-env',
                       '--add-dir']:
            with self.subTest(option=option):
                args = [option, 'update', 'resume', 'thread-id']
                self.assertEqual(self.run_helper(args), ['--yolo', '--remote', 'unix://', *args])
        args = ['--config', 'model="test"', 'app-server', 'daemon', 'version']
        self.assertEqual(self.run_helper(args), ['--yolo', *args])

    def test_explicit_connection_and_local_mode_override_default(self):
        for options in [['--remote', 'unix:///tmp/custom.sock'],
                        ['--remote=unix:///tmp/custom.sock'], ['--no-daemon']]:
            for args in [options + ['resume', 'thread-id'], ['resume', 'thread-id'] + options]:
                with self.subTest(args=args):
                    self.assertEqual(self.run_helper(args), ['--yolo', *args])

    def test_prompt_and_delimiter_are_preserved(self):
        for args in [['--', 'update', '--no-daemon'], ['fix this', 'update'],
                     ['fix "quotes"\nand $shell substitutions `literally`']]:
            with self.subTest(args=args):
                self.assertEqual(self.run_helper(args), ['--yolo', '--remote', 'unix://', *args])

    def test_explicit_yolo_flag_is_not_duplicated(self):
        for flag in ['--yolo', '--dangerously-bypass-approvals-and-sandbox']:
            args = [flag, 'resume', 'thread-id']
            self.assertEqual(self.run_helper(args), ['--remote', 'unix://', *args])

    def test_previous_aliases_can_be_cleared_and_bashrc_sourced_twice(self):
        self.assertEqual(self.run_helper(['resume'], reload=True),
                         ['--yolo', '--remote', 'unix://', 'resume'])
        self.assertEqual(self.run_helper(['resume'], reload=True, command='codex-o'),
                         ['original', '--yolo', '--no-daemon', 'resume'])

    def test_exit_status_is_preserved(self):
        self.assertEqual(self.run_helper(['--version'], exit_code=17),
                         ['--yolo', '--remote', 'unix://', '--version'])

    def test_codex_command_uses_the_fork_and_shared_service(self):
        self.assertEqual(self.run_helper(['resume', 'thread-id'], command='codex'),
                         ['--yolo', '--remote', 'unix://', 'resume', 'thread-id'])

    def test_codex_o_uses_original_binary_directly(self):
        self.assertEqual(self.run_helper(['resume', 'thread-id'], command='codex-o'),
                         ['original', '--yolo', '--no-daemon', 'resume', 'thread-id'])

    def test_original_connection_override_and_maintenance_commands(self):
        for args in [['--remote', 'unix://', 'resume', 'thread-id'],
                     ['--no-daemon', 'resume', 'thread-id'], ['app-server', 'daemon', 'version']]:
            with self.subTest(args=args):
                self.assertEqual(self.run_helper(args, command='codex-o'),
                                 ['original', '--yolo', *args])

    def test_commands_are_discoverable_without_shell_aliases(self):
        for name in ['codex', 'codex-m', 'codex-o']:
            result = subprocess.run(['sh', '-c', 'command -v "$1"', 'test', name],
                                    env=self.env, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), str(self.bin / name))

    def test_reinstall_preserves_package_binaries_and_previous_entries(self):
        binaries = list((self.home / '.codex/packages').glob('*/current/bin/codex'))
        before = {p: p.read_bytes() for p in binaries}
        self.install()
        self.assertEqual(before, {p: p.read_bytes() for p in binaries})
        backups = list((self.home / '.local/state/codex-m-commands').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / 'codex').is_symlink())
        line = 'source "$HOME/.config/codex-m/shell.bash"'
        self.assertEqual((self.home / '.bashrc').read_text().count(line), 1)


if __name__ == '__main__':
    unittest.main()
