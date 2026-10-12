"""Render public screenshots using source UI assets and disposable demo data only."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import os
import subprocess
import threading

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui_fixture', root / 'firmware/mf79u/test-ui-e2e-server.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
fixture.args = SimpleNamespace(timeout=90)
server = fixture.ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    subprocess.run(['node', 'scripts/docs-assets.js'], cwd=root, check=True,
                   env=dict(os.environ, MF79U_DOCS_URL=f'http://127.0.0.1:{server.server_port}'))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=10)
