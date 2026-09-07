"""Local browser interface for the LP solver.

Run ``python app.py`` and open http://127.0.0.1:8000.  The server accepts
only local connections and keeps uploaded model text in memory.
"""
from __future__ import annotations

import json
import tempfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.mps_parser import parse_mps
from src.solver import solve

ROOT = Path(__file__).resolve().parent
MAX_MODEL_BYTES = 10 * 1024 * 1024


class SolverHandler(SimpleHTTPRequestHandler):
    """Serve the UI and a local JSON endpoint for solving uploaded models."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def do_GET(self):
        """Expose the bundled sample through the same local server."""
        if self.path == "/api/sample":
            self._send_json(HTTPStatus.OK, {
                "filename": "sample_small.mps",
                "mpsText": (ROOT / "data" / "sample_small.mps").read_text(encoding="utf-8"),
            })
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/solve":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= MAX_MODEL_BYTES:
                raise ValueError("Model file must be between 1 byte and 10 MB.")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            mps_text = payload.get("mpsText")
            backend = payload.get("backend", "highs")
            max_iterations = int(payload.get("maxIterations", 50_000))
            if not isinstance(mps_text, str) or not mps_text.strip():
                raise ValueError("Choose a non-empty .mps file.")
            if backend not in {"highs", "gpu"}:
                raise ValueError("Backend must be 'highs' or 'gpu'.")
            if not 100 <= max_iterations <= 1_000_000:
                raise ValueError("GPU iterations must be between 100 and 1,000,000.")

            # The parser intentionally receives a temporary file because it
            # operates on standard MPS paths. It is removed immediately.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".mps", encoding="utf-8", delete=False) as f:
                f.write(mps_text)
                temp_path = Path(f.name)
            try:
                model = parse_mps(temp_path)
            finally:
                temp_path.unlink(missing_ok=True)

            if backend == "gpu":
                from src.gpu_solver import solve_gpu_pdhg
                result = solve_gpu_pdhg(model, max_iterations=max_iterations)
            else:
                result = solve(model)

            response = {
                "model": {"name": model.name, "rows": model.num_rows, "columns": model.num_cols, "nonzeros": model.nnz},
                "result": {key: value for key, value in result.items() if key != "x"},
                "variables": [
                    {"name": name, "value": float(value)}
                    for name, value in zip(model.col_names, result["x"])
                ] if result.get("x") is not None else [],
            }
            self._send_json(HTTPStatus.OK, response)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # Return solver errors in a usable form.
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _send_json(self, status: HTTPStatus, payload: dict):
        body = json.dumps(payload, default=self._json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _json_default(value):
        if hasattr(value, "item"):
            return value.item()
        raise TypeError(f"Cannot encode {type(value).__name__}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), SolverHandler)
    print("LP Solver UI running at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
