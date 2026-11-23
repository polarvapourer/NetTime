"""Cross-platform runtime checks, run natively on each CI operating system."""
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from nettime import policy
from nettime.host import ControllerLock, local_macs, parse_macs
from nettime.service import launch_agent
from nettime.store import Store, default_dir, private_ok
from fakes import utc


class Portability(unittest.TestCase):
    def test_timezone_never_uses_host_localtime_or_tzset(self):
        with mock.patch('time.localtime', side_effect=AssertionError('host timezone used')):
            policy.init_tz()
            self.assertEqual(policy.london(utc(2026, 6, 13, 23))['date'], '2026-06-14')
            self.assertEqual(policy.london(utc(2026, 11, 13, 23))['date'], '2026-11-13')

    def test_exact_dst_transitions_across_years(self):
        for year, march, october in [(2026, 29, 25), (2027, 28, 31), (2028, 26, 29), (2030, 31, 27)]:
            self.assertEqual(policy.london(utc(year, 3, march, 0, 59, 59))['minute'], 59)
            self.assertEqual(policy.london(utc(year, 3, march, 1))['minute'], 120)
            self.assertEqual(policy.london(utc(year, 10, october, 0, 59, 59))['minute'], 119)
            self.assertEqual(policy.london(utc(year, 10, october, 1))['minute'], 60)

    def test_timezone_does_not_change_environment(self):
        before = os.environ.get('TZ')
        policy.init_tz(); policy.london(utc(2026, 6, 13, 0))
        self.assertEqual(os.environ.get('TZ'), before)
        with self.assertRaises(ValueError):
            policy.london(utc(1990, 1, 1, 0))

    def test_native_private_storage_and_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(os.path.join(tmp, 'NetTime data'))
            store.save_config({'auth': 'synthetic-test-value'})
            store.save_state(store.load_state())
            for path, mode in [(store.dir, 0o700), (store.config_path, 0o600), (store.state_path, 0o600)]:
                self.assertTrue(private_ok(path, mode), path)
            for n in range(3):
                store.save_config({'iteration': n})
                self.assertEqual(store.load_config()['iteration'], n)
                self.assertTrue(private_ok(store.config_path, 0o600))

    @unittest.skipIf(os.name == "nt", "POSIX ownership and modes")
    def test_refuses_to_read_nonprivate_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            store.save_config({"adapter": "linksys-jnap"})
            os.chmod(store.config_path, 0o644)
            with self.assertRaisesRegex(ValueError, "data must be private"):
                store.load_config()

    @unittest.skipIf(os.name == "nt", "creating symlinks requires Windows privileges")
    def test_rejects_linked_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = os.path.join(tmp, "directory")
            os.mkdir(directory)
            os.chmod(directory, 0o750)
            alias = os.path.join(tmp, "alias")
            os.symlink(directory, alias)
            with self.assertRaisesRegex(ValueError, "ordinary private directory"):
                Store(alias).init()
            self.assertEqual(os.stat(directory).st_mode & 0o777, 0o750)

    def test_lock_rejects_second_process_and_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = 'from nettime.host import ControllerLock; import sys\nwith ControllerLock(sys.argv[1]): pass'
            with ControllerLock(tmp):
                result = subprocess.run([sys.executable, '-c', code, tmp], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'Another controller', result.stderr)
            result = subprocess.run([sys.executable, '-c', code, tmp], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_macs_from_windows_and_macos_outputs(self):
        self.assertEqual(parse_macs('"02-11-22-33-44-55","network"\nether 04:11:22:33:44:66\n00:00:00:00:00:00 ff:ff:ff:ff:ff:ff'),
                         {'02:11:22:33:44:55', '04:11:22:33:44:66'})

    def test_native_identity_discovery(self):
        if sys.platform.startswith('linux') and not os.path.isdir('/sys/class/net'):
            self.skipTest('This container does not expose host interfaces')
        self.assertTrue(local_macs(), 'Native interface discovery failed')

    def test_macos_plist_roundtrip_paths_and_interpreter(self):
        job = launch_agent('/Users/demo/Net Time & code', '/Users/demo/private data', '/opt/python/python3')
        parsed = plistlib.loads(plistlib.dumps(job))
        self.assertEqual(parsed['WorkingDirectory'], '/Users/demo/Net Time & code')
        self.assertEqual(parsed['ProgramArguments'], ['/opt/python/python3', '-m', 'nettime', '--data-dir', '/Users/demo/private data', 'serve'])
        self.assertTrue(parsed['RunAtLoad'] and parsed['KeepAlive'])

    def test_legacy_data_is_not_silently_abandoned(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = os.path.join(tmp, '.local', 'share', 'nettime')
            os.makedirs(legacy)
            with open(os.path.join(legacy, 'config.json'), 'w') as f:
                json.dump({}, f)
            with mock.patch('os.path.expanduser', return_value=tmp):
                self.assertEqual(default_dir(), legacy)

    def test_cli_on_native_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-m', 'nettime', '--data-dir', tmp, 'doctor'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'London time now', result.stdout)
            self.assertIn(b'Not set up yet', result.stdout)


if __name__ == '__main__':
    unittest.main()
