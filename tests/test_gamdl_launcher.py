import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

LAUNCHER = Path(__file__).resolve().parents[1] / 'tools/gamdl.py'


class LifetimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fake = self.root / 'gamdl'
        fake.write_text(f'#!{sys.executable}\nimport pathlib,sys,time\npathlib.Path(sys.argv[2]).touch()\ntime.sleep(float(sys.argv[1]))\nsys.exit(int(sys.argv[3]))\n')
        fake.chmod(0o755)
        (self.root / 'gamdl.json').write_text(json.dumps({'executable': str(fake)}))
        self.bootstrap = self.root / 'run.py'
        self.bootstrap.write_text(f'''import importlib.util, pathlib, sys
spec=importlib.util.spec_from_file_location('launcher', {str(LAUNCHER)!r})
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.STATE=pathlib.Path({str(self.root)!r})
def event(name):
    with (m.STATE/'events').open('a') as f: f.write(name+'\\n')
m.start_vm=lambda: event('up')
m.stop_vm=lambda: event('down')
if '--fail-start' in sys.argv:
    def fail():
        event('up')
        raise RuntimeError('startup failed')
    m.start_vm=fail
sys.exit(m.main(sys.argv[1:]))
''')

    def launch(self, duration, name, code=0, extra=()):
        p = subprocess.Popen([sys.executable, str(self.bootstrap), str(duration), str(self.root / name), str(code), *extra], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        return p

    def wait_ready(self, name):
        for _ in range(100):
            if (self.root / name).exists():
                return
            time.sleep(.02)
        self.fail('gamdl did not start')

    def events(self):
        return (self.root / 'events').read_text().splitlines()

    def test_exit_status_and_cleanup(self):
        p = self.launch(.01, 'one', 7)
        self.assertEqual(p.wait(timeout=5), 7)
        self.assertEqual(self.events(), ['up', 'down'])
        self.assertEqual(json.loads((self.root / 'gamdl-leases.json').read_text()), [])

    def test_overlapping_runs_stop_after_last_exit(self):
        first = self.launch(.3, 'one')
        self.wait_ready('one')
        second = self.launch(1, 'two')
        self.wait_ready('two')
        self.assertEqual(first.wait(timeout=5), 0)
        self.assertEqual(self.events(), ['up'])
        self.assertEqual(second.wait(timeout=5), 0)
        self.assertEqual(self.events(), ['up', 'down'])

    def test_interrupt_stops_child_and_vm(self):
        p = self.launch(60, 'one')
        self.wait_ready('one')
        p.send_signal(signal.SIGINT)
        self.assertEqual(p.wait(timeout=5), 130)
        self.assertEqual(self.events(), ['up', 'down'])

    def test_failed_start_cleans_up(self):
        p = self.launch(.01, 'one', extra=('--fail-start',))
        self.assertNotEqual(p.wait(timeout=5), 0)
        self.assertEqual(self.events(), ['up', 'down'])
        self.assertFalse((self.root / 'one').exists())


if __name__ == '__main__':
    unittest.main()
