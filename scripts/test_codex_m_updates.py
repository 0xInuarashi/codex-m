import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import patch

import codex_m_updates as updates


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.home_patch = patch.object(Path, 'home', return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.repo = self.base / 'repo'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.repo)], check=True)
        updates.git(self.repo, 'config', 'user.name', 'Test')
        updates.git(self.repo, 'config', 'user.email', 'test@example.invalid')
        self.commit('base', 'base')
        updates.git(self.repo, 'update-ref', 'refs/remotes/upstream/main', 'HEAD')

    def commit(self, name, value):
        (self.repo / name).write_text(value)
        updates.git(self.repo, 'add', name)
        updates.git(self.repo, 'commit', '-qm', name)

    def make_release(self):
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        for name in ('codex-m', 'codex_m_updates.py', 'codex-m.defaults.toml'):
            (scripts / name).write_text('# fixture\n')
        binary_dir = self.repo / 'codex-rs/target/dev-small'
        binary_dir.mkdir(parents=True)
        for name in updates.BINARIES:
            binary = binary_dir / name
            binary.write_text('#!/bin/sh\necho codex-m-test\n')
            binary.chmod(0o755)
        return binary_dir

    def test_install_switches_complete_release_and_preserves_config(self):
        self.make_release()
        config = self.home / '.config/codex-m/config.toml'
        config.parent.mkdir(parents=True)
        config.write_text('service_tier = "flex"\n')
        updates.install(self.repo)
        previous = (updates.install_home() / 'current').resolve()
        updates.install(self.repo)
        self.assertNotEqual(previous, (updates.install_home() / 'current').resolve())
        self.assertTrue((previous / 'codex').exists())
        self.assertEqual(config.read_text(), 'service_tier = "flex"\n')
        self.assertEqual(updates.manifest()['commit'], updates.git(self.repo, 'rev-parse', 'HEAD'))

    def test_missing_binary_does_not_replace_install(self):
        binaries = self.make_release()
        updates.install(self.repo)
        previous = (updates.install_home() / 'current').resolve()
        (binaries / 'codex-exec-server').unlink()
        with self.assertRaises(RuntimeError):
            updates.install(self.repo)
        self.assertEqual(previous, (updates.install_home() / 'current').resolve())

    def test_failed_smoke_test_does_not_replace_install(self):
        binaries = self.make_release()
        updates.install(self.repo)
        previous = (updates.install_home() / 'current').resolve()
        (binaries / 'codex').write_text('#!/bin/sh\nexit 1\n')
        with self.assertRaises(subprocess.CalledProcessError):
            updates.install(self.repo)
        self.assertEqual(previous, (updates.install_home() / 'current').resolve())
        self.assertEqual(len(list((updates.install_home() / 'releases').iterdir())), 1)

    def test_prepare_keeps_source_unchanged(self):
        original = updates.git(self.repo, 'rev-parse', 'HEAD')
        remote = self.base / 'remote'
        subprocess.run(['git', 'clone', '-q', str(self.repo), str(remote)], check=True)
        updates.git(remote, 'config', 'user.name', 'Test')
        updates.git(remote, 'config', 'user.email', 'test@example.invalid')
        (remote / 'update').write_text('new upstream work')
        updates.git(remote, 'add', 'update')
        updates.git(remote, 'commit', '-qm', 'update')
        with patch.object(updates, 'UPSTREAM', str(remote)):
            prepared = updates.prepare(self.repo, str(remote), 'main')
        self.assertEqual(updates.git(self.repo, 'rev-parse', 'HEAD'), original)
        self.assertFalse((self.repo / 'update').exists())
        self.assertTrue((prepared / 'update').exists())

    def test_prepare_rejects_divergence(self):
        remote = self.base / 'remote'
        subprocess.run(['git', 'clone', '-q', str(self.repo), str(remote)], check=True)
        self.commit('local', 'preserve me')
        head = updates.git(self.repo, 'rev-parse', 'HEAD')
        with self.assertRaises(RuntimeError):
            updates.prepare(self.repo, str(remote), 'main')
        self.assertEqual(updates.git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_prepare_rejects_dirty_source_before_fetch(self):
        (self.repo / 'local').write_text('unsaved work')
        with self.assertRaises(RuntimeError):
            updates.prepare(self.repo, 'must-not-be-fetched', 'main')

    def test_cached_check_does_not_need_network(self):
        installed = {'commit': 'aaa', 'upstream_commit': 'bbb'}
        with patch.object(updates, 'manifest', return_value=installed), \
             patch.object(updates, 'remote_head', side_effect=['ccc', 'ddd']) as remote:
            first = updates.check()
            second = updates.check()
        self.assertEqual(first, second)
        self.assertEqual(remote.call_count, 2)
        self.assertIn('codex-m update', updates.describe(first))

    def test_upstream_pending_is_not_an_installable_update(self):
        data = {'installed': 'aaa', 'fork': 'aaa', 'upstream': 'bbb', 'installed_upstream': 'ccc'}
        self.assertIn('awaiting integration', updates.describe(data))

    def test_build_failure_never_installs(self):
        with patch.object(updates, 'manifest', return_value={'source': str(self.repo)}), \
             patch.object(updates, 'prepare', return_value=self.repo), \
             patch.object(updates, 'run', side_effect=subprocess.CalledProcessError(1, 'build')), \
             patch.object(updates, 'install') as install:
            with self.assertRaises(subprocess.CalledProcessError):
                updates.update()
            install.assert_not_called()

    def test_first_startup_refreshes_in_background_without_network_wait(self):
        with patch.object(updates, 'manifest', return_value={'commit': 'aaa'}), \
             patch.object(subprocess, 'Popen') as refresh, \
             patch.object(updates, 'remote_head') as remote:
            self.assertIsNone(updates.startup_check())
            refresh.assert_called_once()
            remote.assert_not_called()

    def test_noninteractive_startup_does_not_check_network(self):
        with patch.object(sys.stdin, 'isatty', return_value=False), \
             patch.object(updates, 'check') as check:
            updates.startup_notice()
            check.assert_not_called()

    def test_failed_interactive_update_continues_with_installed_binary(self):
        data = {'fork': 'new', 'installed': 'old'}
        with patch.object(sys.stdin, 'isatty', return_value=True), \
             patch.object(sys.stderr, 'isatty', return_value=True), \
             patch.object(updates, 'startup_check', return_value=data), \
             patch('builtins.input', return_value='yes'), \
             patch.object(updates, 'update', side_effect=RuntimeError('test build failure')), \
             patch('builtins.print') as output:
            updates.startup_notice()
            self.assertTrue(any('Continuing with the installed version' in str(call) for call in output.call_args_list))

    def test_launcher_preserves_command_delimiter(self):
        binary = updates.install_home() / 'codex'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n')
        binary.chmod(0o755)
        launcher = Path(__file__).resolve().parent / 'codex-m'
        arguments = ['exec', '--', 'some-command', '--flag']
        result = subprocess.run([sys.executable, str(launcher), *arguments],
                                env=dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / '.codex')),
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)[-len(arguments):], arguments)
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
