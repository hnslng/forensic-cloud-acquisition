"""HTTPS GitHub release fixture, disposable CI runner only; no tokens."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import sys

root=Path(sys.argv[1]).resolve()
class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass
server=ThreadingHTTPServer(('0.0.0.0',443),partial(Handler,directory=str(root)))
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(sys.argv[2],sys.argv[3])
server.socket=context.wrap_socket(server.socket,server_side=True)
server.serve_forever()
