#!/usr/bin/env python3
"""Run the installed gamdl with a shared, temporary wrapper VM lifetime."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / '.local'
active = None
interrupted = None


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


@contextlib.contextmanager
def locked():
    with (STATE / 'gamdl.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def leases():
    path = STATE / 'gamdl-leases.json'
    current = json.loads(path.read_text()) if path.exists() else []
    alive = []
    for pid in current:
        try:
            os.kill(pid, 0)
            alive.append(pid)
        except ProcessLookupError:
            pass
    return alive


def received(sig, _frame):
    global interrupted
    interrupted = sig
    if active is not None and active.poll() is None:
        active.send_signal(sig)


def run(args, **kwargs):
    global active
    if interrupted:
        raise InterruptedError('Interrupted')
    active = subprocess.Popen(args, **kwargs)
    try:
        result = active.wait()
    finally:
        active = None
    if interrupted:
        raise InterruptedError('Interrupted')
    return result


def vm_command(*args):
    with (STATE / 'gamdl-lifecycle.log').open('a') as log:
        result = run(['limactl', *args], stdout=log, stderr=log)
    if result:
        raise RuntimeError(f'VM command failed; see {STATE / "gamdl-lifecycle.log"}')


def start_vm():
    print('Starting wrapper…', file=sys.stderr)
    vm_command('start', '--tty=false', 'wrapper-v2')
    vm_command('shell', 'wrapper-v2', 'sudo', 'systemctl', 'start', 'wrapper-v2.service')
    port = json.loads((STATE / 'ports.json').read_text())['http']
    # Read the worker snapshot without logging or saving any authentication data.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(30):
        if interrupted:
            raise InterruptedError('Interrupted')
        try:
            with opener.open(f'http://127.0.0.1:{port}/me', timeout=3) as response:
                if json.load(response).get('runtime', {}).get('playback_ready'):
                    return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError('Apple playback runtime is unavailable; run bash tools/macos.sh logs')


def stop_vm():
    print('Stopping wrapper…', file=sys.stderr)
    with (STATE / 'gamdl-lifecycle.log').open('a') as log:
        result = subprocess.run(['limactl', 'stop', '--tty=false', 'wrapper-v2'], stdout=log, stderr=log)
    if result.returncode:
        print(f'Could not stop wrapper; see {STATE / "gamdl-lifecycle.log"}', file=sys.stderr)


def install():
    STATE.mkdir(exist_ok=True)
    config = STATE / 'gamdl.json'
    executable = shutil.which('gamdl')
    if executable and Path(executable).resolve() != Path(__file__).resolve():
        save(config, {'executable': executable})
    if not config.exists():
        raise RuntimeError('Install gamdl first, then rerun this installer')
    target = Path.home() / '.local/bin/gamdl'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.resolve() != Path(__file__).resolve():
            raise RuntimeError(f'{target} already exists; preserving it')
    else:
        target.symlink_to(Path(__file__).resolve())
    print(f'Installed {target}')


def main(args):
    global interrupted
    executable = json.loads((STATE / 'gamdl.json').read_text())['executable']
    if any(arg in ('--help', '-h', '--version') for arg in args) or not args:
        return subprocess.call([executable, *args])
    signal.signal(signal.SIGINT, received)
    signal.signal(signal.SIGTERM, received)
    registered = False
    try:
        with locked():
            current = leases()
            first = not current
            if first:
                try:
                    start_vm()
                except BaseException:
                    signal.signal(signal.SIGINT, signal.SIG_IGN)
                    signal.signal(signal.SIGTERM, signal.SIG_IGN)
                    stop_vm()
                    raise
            current.append(os.getpid())
            save(STATE / 'gamdl-leases.json', current)
            registered = True
        result = run([executable, *args])
        return result if result >= 0 else 128 - result
    except InterruptedError:
        return 128 + (interrupted or signal.SIGINT)
    finally:
        # Finish shutdown even if Ctrl+C is pressed again while stopping Lima.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if registered:
            with locked():
                current = [pid for pid in leases() if pid != os.getpid()]
                save(STATE / 'gamdl-leases.json', current)
                if not current:
                    stop_vm()


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--install-launcher']:
            install()
            sys.exit(0)
        sys.exit(main(sys.argv[1:]))
    except (OSError, ValueError, RuntimeError) as error:
        print(f'gamdl: {error}', file=sys.stderr)
        sys.exit(1)
