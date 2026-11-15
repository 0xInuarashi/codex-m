"""Release-only changes must advance the fork without hiding source conflicts."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('update-codex-m-version.py').resolve()
spec = importlib.util.spec_from_file_location('fork_version', SCRIPT)
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


class VersionTest(unittest.TestCase):
    def test_stable_tag_and_no_downgrade(self):
        self.assertEqual(version.fork_version('rust-v0.169.0', '0.167.0-codex-m.1'), '0.169.0-codex-m.1')
        for tag in ['rust-v0.169.0-alpha.1', 'rusty-v8-v150.4.0', 'rust-v0.166.0']:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                version.fork_version(tag, '0.167.0-codex-m.1')

    def test_only_workspace_version_changes(self):
        source = '[workspace.package]\nversion = "0.167.0-codex-m.1"\n\n[dependencies]\nother = { version = "0.167.0-codex-m.1" }\n'
        result = version.replace_version(source, '0.169.0-codex-m.1')
        self.assertIn('other = { version = "0.167.0-codex-m.1" }', result)
        self.assertEqual(result.count('0.169.0-codex-m.1'), 1)

    def test_real_merge_resolves_only_version_conflicts(self):
        for source_conflict in [False, True]:
            with self.subTest(source_conflict=source_conflict), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                env = dict(os.environ, GIT_AUTHOR_NAME='Test', GIT_COMMITTER_NAME='Test',
                           GIT_AUTHOR_EMAIL='test@example.com', GIT_COMMITTER_EMAIL='test@example.com')

                def git(*args, check=True):
                    return subprocess.run(['git', *args], cwd=root, env=env, text=True,
                                          capture_output=True, check=check)

                def manifest(value, edition):
                    return f'[workspace.package]\nversion = "{value}"\nedition = "{edition}"\n'

                git('init', '-b', 'fork')
                path = root / version.MANIFEST
                path.parent.mkdir()
                path.write_text(manifest('0.0.0', '2024'))
                git('add', '.')
                git('commit', '-m', 'base')
                git('branch', 'upstream')
                path.write_text(manifest('0.167.0-codex-m.1', '2027' if source_conflict else '2024'))
                git('commit', '-am', 'fork version')
                git('checkout', 'upstream')
                path.write_text(manifest('0.169.0', '2026' if source_conflict else '2024'))
                git('commit', '-am', 'stable release')
                git('checkout', 'fork')
                self.assertNotEqual(git('merge', '--no-edit', 'upstream', check=False).returncode, 0)
                before = path.read_text()
                result = subprocess.run(['python3', str(SCRIPT), 'rust-v0.169.0', '--resolve-merge'],
                                        cwd=root, capture_output=True, text=True)
                if source_conflict:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(path.read_text(), before)
                    self.assertIn(version.MANIFEST, git('diff', '--name-only', '--diff-filter=U').stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(path.read_text(), manifest('0.169.0-codex-m.1', '2024'))
                    self.assertEqual(git('diff', '--name-only', '--diff-filter=U').stdout, '')


if __name__ == '__main__':
    unittest.main()
