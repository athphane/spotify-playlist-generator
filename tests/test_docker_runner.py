import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class DockerRunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='playlist-runner-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.project = self.directory / 'project with spaces'
        (self.project / 'scripts').mkdir(parents=True)
        source = Path(__file__).resolve().parents[1]
        self.runner = self.project / 'cron.sh'
        # Exercise rotation without generating tens of MiB for each test.
        self.runner.write_text((source / 'cron.sh').read_text().replace(
            '$((10 * 1024 * 1024))', '64'))
        self.runner.chmod(0o755)
        shutil.copy2(source / 'scripts/prepare-data.sh',
                     self.project / 'scripts/prepare-data.sh')
        (self.project / 'config.ini').write_text('[spotify]\n')
        binaries = self.directory / 'bin'
        binaries.mkdir()
        self.output = self.directory / 'output'
        self.invocations = self.directory / 'invocations'
        docker = binaries / 'docker'
        docker.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n" "$@" >> "$PLAYLIST_TEST_INVOCATIONS"\n'
            'cat "$PLAYLIST_TEST_OUTPUT"\n'
            'exit "${PLAYLIST_TEST_EXIT_CODE:-0}"\n')
        docker.chmod(0o755)
        self.environment = {
            **os.environ,
            'PATH': f'{binaries}:{os.defpath}',
            'PLAYLIST_TEST_OUTPUT': str(self.output),
            'PLAYLIST_TEST_INVOCATIONS': str(self.invocations),
        }

    def run_job(self, payload=b'', exit_code=0, args=()):
        self.output.write_bytes(payload)
        return subprocess.run(
            [str(self.runner), *args], cwd=self.directory,
            env={**self.environment, 'PLAYLIST_TEST_EXIT_CODE': str(exit_code)},
            capture_output=True, timeout=10)

    def retained_output(self):
        output = b''
        for name in ('playlist.log.3', 'playlist.log.2',
                     'playlist.log.1', 'playlist.log'):
            path = self.project / name
            if path.exists():
                self.assertLessEqual(path.stat().st_size, 64)
                output += path.read_bytes()
        self.assertLessEqual(len(list(self.project.glob('playlist.log*'))), 4)
        return output

    def test_default_job_and_explicit_arguments_from_another_directory(self):
        for args, expected in (
            ((), ['up', '--no-color', '--exit-code-from', 'playlist', 'playlist']),
            (('--help',), ['run', '--rm', '-T', '--interactive=false',
                          'playlist', '--help']),
        ):
            with self.subTest(args=args):
                self.invocations.write_text('')
                result = self.run_job(b'job output\n', args=args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.invocations.read_text().splitlines(), [
                    'compose', '--project-directory', str(self.project),
                    '--file', str(self.project / 'compose.yaml'), *expected])

    def test_migration_preserves_state_and_never_overwrites_container_updates(self):
        for filename in ('.cache', 'playlists.json'):
            (self.project / filename).write_text('existing state')
        self.assertEqual(self.run_job().returncode, 0)
        for filename in ('.cache', 'playlists.json'):
            migrated = self.project / 'data' / filename
            self.assertEqual(migrated.read_text(), 'existing state')
            migrated.write_text('container update')
        self.assertEqual(self.run_job().returncode, 0)
        for filename in ('.cache', 'playlists.json'):
            self.assertEqual((self.project / 'data' / filename).read_text(),
                             'container update')

    def test_missing_config_fails_before_starting_docker(self):
        (self.project / 'config.ini').unlink()
        result = self.run_job()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'config.ini', result.stderr)
        self.assertFalse(self.invocations.exists())

    def test_rotation_retains_recent_unicode_output_across_runs(self):
        first = ''.join(f'{i}: playlist 🍌\n' for i in range(30)).encode()
        second = ''.join(f'{i}: updated 🍎\n' for i in range(30, 60)).encode()
        self.assertEqual(self.run_job(first).returncode, 0)
        self.assertEqual(self.run_job(second).returncode, 0)
        retained = self.retained_output()
        self.assertTrue((first + second).endswith(retained))
        self.assertIn('59: updated 🍎\n'.encode(), retained)
        for path in self.project.glob('playlist.log*'):
            path.read_text()  # Ordinary lines remain valid UTF-8.

    def test_oversized_line_and_preexisting_log_stay_bounded(self):
        (self.project / 'playlist.log').write_bytes(b'old ' * 100)
        payload = b'x' * 600 + b'\n'
        self.assertEqual(self.run_job(payload).returncode, 0)
        self.assertTrue(payload.endswith(self.retained_output()))
        self.assertEqual(len(list(self.project.glob('playlist.log*'))), 4)

    def test_failed_container_status_is_preserved(self):
        for args in ((), ('--help',)):
            with self.subTest(args=args):
                self.assertEqual(self.run_job(b'failure\n' * 40, 23, args).returncode,
                                 23)
                self.assertTrue(self.retained_output().endswith(b'failure\n'))

    def test_overlapping_run_skips_docker_and_log_rotation(self):
        log = self.project / 'playlist.log'
        log.write_bytes(b'unchanged\n')
        with (self.project / '.playlist.lock').open('a') as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.run_job(b'not written\n').returncode, 0)
        self.assertFalse(self.invocations.exists())
        self.assertEqual(list(self.project.glob('playlist.log*')), [log])
        self.assertEqual(log.read_bytes(), b'unchanged\n')

    def test_log_write_failure_is_reported(self):
        (self.project / 'playlist.log').mkdir()
        self.assertNotEqual(self.run_job(b'cannot write\n').returncode, 0)


if __name__ == '__main__':
    unittest.main()
