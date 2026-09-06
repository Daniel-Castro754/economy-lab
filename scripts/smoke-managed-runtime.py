"""Install NSIS, prepare engines through the frozen API, restart and simulate."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen


def main():
    installer = Path(sys.argv[1]).resolve()
    report = Path('managed-runtime-smoke.json').resolve()
    with tempfile.TemporaryDirectory(prefix='Economy Lab installed test ') as temporary:
        root = Path(temporary)
        installed = root / 'Application'
        subprocess.run([str(installer), '/S', '/D=' + str(installed)], check=True, timeout=180)
        executable = installed / 'economy-lab-backend.exe'
        resources = installed / 'runtime-tools'
        assert executable.is_file(), list(installed.iterdir())
        assert (resources / 'uv.exe').is_file(), list(resources.iterdir())
        env = dict(os.environ, ECONOMY_LAB_DATA_DIR=str(root / 'User data'),
                   ECONOMY_LAB_RUNTIME_MODE='desktop-sidecar',
                   ECONOMY_LAB_RUNTIME_RESOURCES=str(resources),
                   ECONOMY_LAB_SHUTDOWN_TOKEN='managed-smoke-shutdown')
        # No user/system Python must be needed to bootstrap the managed runtime.
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        env['PATH'] = os.pathsep.join([os.environ['SystemRoot'] + r'\System32', os.environ['SystemRoot']])
        process = None
        base = ''

        def api(path, payload=None, method=None, headers=None):
            request = Request(base + path, data=None if payload is None else json.dumps(payload).encode(),
                method=method, headers={'Origin': 'http://tauri.localhost', 'Content-Type': 'application/json', **(headers or {})})
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())

        def start():
            nonlocal process, base
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            base = f'http://127.0.0.1:{port}/api/v1'
            process = subprocess.Popen([str(executable), '--port', str(port)], env=env)
            deadline = time.monotonic() + 90
            while True:
                try:
                    return api('/health')
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Installed backend did not start')
                    time.sleep(.5)

        def stop():
            if process is None or process.poll() is not None:
                return
            try:
                api('/runtime/shutdown', method='POST', headers={'X-Economy-Lab-Shutdown-Token': 'managed-smoke-shutdown'})
                process.wait(timeout=20)
            except Exception:
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], check=False)
                process.wait(timeout=10)

        try:
            initial = start()
            assert not initial['hark_available'] and not initial['mesa_available'], initial
            state = api('/runtime/engines')
            assert state['installer_available'], state
            state = api('/runtime/engines/install', method='POST')
            deadline = time.monotonic() + 1500
            last_message = ''
            while state['state'] == 'installing':
                if time.monotonic() > deadline:
                    raise RuntimeError('Managed installation timed out')
                if state['message'] != last_message:
                    print(state['message'], flush=True)
                    last_message = state['message']
                time.sleep(2)
                state = api('/runtime/engines')
            print(api('/runtime/engines/log')['log'], flush=True)
            assert state['state'] == 'ready' and state['restart_required'], state
            python = Path(state['managed_python'])
            # The PATH command must use precisely the environment selected by the app.
            command_dir = Path(state['commands_directory'])
            command = command_dir / 'economy-lab-python.cmd'
            pip_command = command_dir / 'economy-lab-pip.cmd'
            assert command.is_file() and pip_command.is_file()
            output = subprocess.check_output(['cmd.exe', '/c', str(pip_command), '--version'], text=True)
            assert str(python.parent.parent).lower() in output.lower(), output
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
                user_path, _ = winreg.QueryValueEx(key, 'Path')
            assert str(command_dir).lower() in user_path.lower()
            stop()
            active = start()
            assert active['hark_available'] and active['mesa_available'], active
            state = api('/runtime/engines')
            assert state['backend_kind'] == 'managed' and not state['restart_required'], state
            scenario = {'name': 'Installed managed engines', 'months': 1, 'households': 100, 'firms': 5,
                        'banks': 1, 'activation_engine': 'mesa', 'household_behavior': 'hark', 'seed': 42}
            job = api('/jobs/simulations', {'scenario': scenario, 'timeout_seconds': 300})
            deadline = time.monotonic() + 310
            while job['status'] in ('queued', 'running'):
                if time.monotonic() > deadline:
                    raise RuntimeError('Managed simulation timed out')
                time.sleep(.5)
                job = api('/jobs/' + job['id'])
            assert job['status'] == 'completed', job
            for key in ('ledger_balanced', 'godley_stocks_balanced', 'godley_flows_balanced'):
                assert job['result']['summary'][key], key
            result = {'version': active['engine_version'], 'nsis_installed': True, 'bootstrap_without_system_python': True,
                      'mesa': True, 'hark': True, 'managed_restart': True, 'user_path': True,
                      'pip_targets_managed_environment': True, 'economy_zero': 'completed', 'ledger_balanced': True}
            report.write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result), flush=True)
        finally:
            try:
                if process and process.poll() is None:
                    Path('managed-installation.log').write_text(api('/runtime/engines/log')['log'], encoding='utf-8')
            finally:
                stop()
            # NSIS and PATH were tested in a disposable runner, but remove the test path.
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                    value, kind = winreg.QueryValueEx(key, 'Path')
                    value = ';'.join(p for p in value.split(';') if not p.lower().startswith(str(root).lower()))
                    winreg.SetValueEx(key, 'Path', 0, kind, value)
            except OSError:
                pass


if __name__ == '__main__':
    main()
