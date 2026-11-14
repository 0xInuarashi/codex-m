"""Exercise the sourced Bash helper without starting real Codex sessions."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HELPER = Path(__file__).with_name('codex-m-shell.bash')


@unittest.skipUnless(shutil.which('bash'), 'Bash is required')
class ShellDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='codex-m-shell-')
        self.addCleanup(temporary.cleanup)
        self.bin = Path(temporary.name)
        stub = self.bin / 'codex-m'
        stub.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\nexit "${CODEX_M_TEST_EXIT:-0}"\n')
        stub.chmod(0o755)
        original = self.bin / 'codex'
        original.write_text('#!/bin/bash\nprintf "%s\\0" original "$@"\n')
        original.chmod(0o755)

    def run_helper(self, arguments, *, exit_code=0, reload=False, command='codex-m'):
        source = 'shopt -s expand_aliases\n. "$1"\nshift\n' + command + ' "$@"'
        if reload:
            source = 'shopt -s expand_aliases\nalias codex-m="codex-m --yolo"\n. "$1"\n' + source
        result = subprocess.run(
            ['bash', '--noprofile', '--norc', '-c', source, 'shell-test', str(HELPER), *arguments],
            env={**os.environ, 'PATH': f'{self.bin}:/usr/bin:/bin',
                 'CODEX_M_TEST_EXIT': str(exit_code)},
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

    def test_previous_alias_can_be_replaced_and_helper_can_be_sourced_twice(self):
        self.assertEqual(self.run_helper(['resume'], reload=True),
                         ['--yolo', '--remote', 'unix://', 'resume'])

    def test_exit_status_is_preserved(self):
        self.assertEqual(self.run_helper(['--version'], exit_code=17),
                         ['--yolo', '--remote', 'unix://', '--version'])

    def test_codex_alias_uses_the_fork_and_shared_service(self):
        self.assertEqual(self.run_helper(['resume', 'thread-id'], command='codex'),
                         ['--remote', 'unix://', '--yolo', 'resume', 'thread-id'])

    def test_codex_o_bypasses_codex_alias_and_uses_original_binary(self):
        self.assertEqual(self.run_helper(['resume', 'thread-id'], command='codex-o'),
                         ['original', '--yolo', 'resume', 'thread-id'])


if __name__ == '__main__':
    unittest.main()
