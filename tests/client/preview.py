"""Serve the client with the frozen mock; development only, no live AI."""
import argparse
import importlib.util
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8003)
    parser.add_argument('--api-port', type=int, default=8001)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('samepage_mock', ROOT / 'contracts/mock_api.py')
    mock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mock)
    api = ThreadingHTTPServer(('127.0.0.1', args.api_port), mock.Handler)
    Thread(target=api.serve_forever, daemon=True).start()

    class PreviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT / 'frontend'), **kw)

        def do_GET(self):
            if self.path.split('?')[0] in ('/client', '/client/', '/client/index.html'):
                html = (ROOT / 'frontend/client/index.html').read_text()
                settings = ('<script>window.SAMEPAGE_API_BASE="http://127.0.0.1:'
                            + str(args.api_port) + '";window.SAMEPAGE_MOCK_MODE=true;</script>')
                body = html.replace('<head>', '<head>' + settings, 1).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                super().do_GET()

    print(f'Client preview: http://127.0.0.1:{args.port}/client (mock only)', flush=True)
    try:
        ThreadingHTTPServer(('127.0.0.1', args.port), PreviewHandler).serve_forever()
    finally:
        api.shutdown()


if __name__ == '__main__':
    main()
