"""Check the real frozen backend with isolated data before accepting an installer."""
from concurrent.futures import ThreadPoolExecutor
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
    executable = Path(sys.argv[1]).resolve()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    token = 'smoke-test-local-shutdown'
    with tempfile.TemporaryDirectory(prefix='economy-lab-smoke-') as data_dir:
        env = dict(os.environ, ECONOMY_LAB_DATA_DIR=data_dir,
                   ECONOMY_LAB_RUNTIME_MODE='desktop-sidecar',
                   ECONOMY_LAB_SHUTDOWN_TOKEN=token)
        process = subprocess.Popen([str(executable), '--port', str(port)], env=env)
        base = f'http://127.0.0.1:{port}/api/v1'

        def api(path, payload=None, method=None, extra_headers=None):
            headers = {'Content-Type': 'application/json', 'Origin': 'http://tauri.localhost'}
            headers.update(extra_headers or {})
            request = Request(base + path, data=None if payload is None else json.dumps(payload).encode(),
                              headers=headers, method=method)
            with urlopen(request, timeout=30) as response:
                raw = response.read()
                return response, json.loads(raw) if 'json' in response.headers.get('Content-Type', '') else raw

        try:
            deadline = time.monotonic() + 90
            while True:
                try:
                    _, health = api('/health')
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('Packaged backend did not become ready')
                    time.sleep(.25)
            assert health['engine_version'] == '2.14.0', health
            response, scenarios = api('/simple/scenarios')
            assert len(scenarios) == 3
            assert response.headers.get('Access-Control-Allow-Origin') == 'http://tauri.localhost'
            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(lambda _: api('/storage/status')[1], range(8)))
            assert all(status['schema_version'] == 5 for status in statuses)
            scenario = {'name': 'Packaged smoke', 'months': 12, 'households': 300, 'firms': 15, 'banks': 3, 'seed': 42}
            _, project = api('/projects', {'name': 'Packaged smoke', 'scenario': scenario})
            _, job = api('/jobs/simulations', {'scenario': scenario, 'project_id': project['id'], 'timeout_seconds': 120})
            deadline = time.monotonic() + 130
            while job['status'] in ('queued', 'running'):
                if time.monotonic() >= deadline:
                    raise RuntimeError('Job did not finish in time')
                time.sleep(.25)
                _, job = api('/jobs/' + job['id'])
            assert job['status'] == 'completed', job
            assert len(job['result']['series']) == 12
            for key in ('ledger_balanced', 'godley_stocks_balanced', 'godley_flows_balanced'):
                assert job['result']['summary'][key], key
            _, exported = api('/exports/simulation.xlsx', {'scenario': job['scenario'], 'result': job['result']})
            assert exported[:2] == b'PK'
            _, runs = api(f"/projects/{project['id']}/runs")
            assert len(runs) == 1
            print(json.dumps({'version': health['engine_version'], 'scenarios': len(scenarios),
                              'months': 12, 'persisted_runs': len(runs), 'accounting_balanced': True,
                              'xlsx_bytes': len(exported)}))
        finally:
            try:
                api('/runtime/shutdown', method='POST', extra_headers={'X-Economy-Lab-Shutdown-Token': token})
                process.wait(timeout=10)
            except Exception:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
