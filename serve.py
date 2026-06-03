"""Tiny static server that reads PORT env var (for Claude preview autoPort)."""
import os, sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

port = int(os.environ.get("PORT", 8765))
docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
os.chdir(docs)
print(f"Serving {docs} on http://localhost:{port}", flush=True)
HTTPServer(("", port), SimpleHTTPRequestHandler).serve_forever()
