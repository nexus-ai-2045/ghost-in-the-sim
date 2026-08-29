"""依存追加なしでデモUIを配信する開発用サーバー。"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="ghost-in-the-sim demo UI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8045)
    args = parser.parse_args()
    web_root = Path(__file__).resolve().parents[1] / "web"
    handler = partial(SimpleHTTPRequestHandler, directory=web_root)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
