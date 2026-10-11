"""Start FinSight and open its local web page."""

import json
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
HOST = "127.0.0.1"
PORTS = range(8000, 8011)

# The backend uses simple local imports (database, models, etc.).
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    for port in PORTS:
        url = f"http://{HOST}:{port}"
        try:
            with urlopen(f"{url}/api", timeout=0.3) as response:
                health = json.loads(response.read())
                if health.get("message") == "FinSight is running" and health.get("server_version") == 2:
                    print(f"FinSight is already running at {url}", flush=True)
                    webbrowser.open(url)
                    return
        except (OSError, ValueError):
            pass

    port = next(
        (candidate for candidate in PORTS if _port_is_available(candidate)),
        None,
    )
    if port is None:
        raise SystemExit("No free local port found between 8000 and 8010.")
    url = f"http://{HOST}:{port}"

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "FinSight dependencies are missing. Install them with: "
            "pip install -r backend/requirements.txt"
        ) from exc

    print(f"FinSight is starting at {url}", flush=True)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run("main:app", host=HOST, port=port, app_dir=str(BACKEND_DIR))


def _port_is_available(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


if __name__ == "__main__":
    main()