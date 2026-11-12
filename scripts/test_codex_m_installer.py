"""Exercise the adapted installer with upstream's fake release/download harness."""
from pathlib import Path
import unittest
import tempfile
import subprocess

root = Path(__file__).resolve().parents[1]
source = (root / 'scripts/install/test_install_sh.py').read_text()
source = source.replace('github.com/openai/codex/', 'github.com/0xInuarashi/codex-m/')
source = source.replace('api.github.com/repos/openai/codex/', 'api.github.com/repos/0xInuarashi/codex-m/')
source = source.replace('INSTALL_SCRIPT = Path(__file__).with_name("install.sh")', f'INSTALL_SCRIPT = Path({str(root / "install.sh")!r})')
source = source.replace('VERSION = "0.142.5"', 'VERSION = "0.167.0-codex-m.10"')
namespace = {'__name__': 'fork_installer_harness', '__file__': str(root / 'scripts/install/test_install_sh.py')}
exec(compile(source, str(root / 'scripts/install/test_install_sh.py'), 'exec'), namespace)
namespace['INSTALL_SCRIPT'] = root / 'install.sh'

class ForkInstallerTest(unittest.TestCase):
    def test_native_install_preserves_official_command_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            archive, checksum, metadata = namespace['create_package_release'](path, target='x86_64-unknown-linux-musl', include_exec_server=True)
            installed_bin = path / 'install-bin'
            installed_bin.mkdir()
            official = installed_bin / 'codex'
            official.write_text('official installation')
            result, requests = namespace['run_installer_in'](path, 'latest', metadata_json=metadata, archive_path=archive, checksum_path=checksum)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(official.read_text(), 'official installation')
            installed = installed_bin / 'codex-m'
            self.assertTrue(installed.is_symlink())
            self.assertIn('/packages/codex-m/', str(installed.resolve()))
            self.assertIn(namespace['VERSION'], subprocess.check_output([installed, '--version'], text=True))
            self.assertTrue(all('0xInuarashi/codex-m/' in url for url in requests))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            archive, checksum, metadata = namespace['create_package_release'](path, target='x86_64-unknown-linux-musl')
            archive.write_bytes(b'corrupt download')
            result, _ = namespace['run_installer_in'](path, 'latest', metadata_json=metadata, archive_path=archive, checksum_path=checksum)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((path / 'install-bin/codex-m').exists())

    def test_upstream_metadata_validation_and_release_download(self):
        for name in (
            'test_metadata_fetch_failure_is_not_reported_as_missing_assets',
            'test_exact_release_opt_out_uses_github_metadata_once',
            'test_latest_release_reuses_version_metadata',
            'test_compact_metadata_is_independent_of_field_order',
            'test_json_like_strings_and_nested_fields_do_not_define_assets',
        ):
            with self.subTest(name=name):
                getattr(namespace['InstallShTest'](), name)()

if __name__ == '__main__':
    unittest.main()
