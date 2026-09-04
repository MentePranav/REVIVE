"""
CLI launcher for the REVIVE Interactive Control Center Web Server.
Supports local development and production container/cloud binding via PORT and HOST env vars.
Usage:
    python -m server.cli --port 8000 --host 127.0.0.1
"""

import argparse
import sys
import uvicorn

from core.config import APP_CONFIG

# Ensure UTF-8 stdout
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    default_port = APP_CONFIG.port
    default_host = APP_CONFIG.host

    parser = argparse.ArgumentParser(description="REVIVE Interactive Control Center Server")
    parser.add_argument("--port", "-p", type=int, default=default_port, help=f"HTTP port to bind (default: {default_port})")
    parser.add_argument("--host", "-H", type=str, default=default_host, help=f"Network host interface (default: {default_host})")
    parser.add_argument("--reload", "-r", action="store_true", help="Enable auto-reload on code change")

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("      REVIVE — AUTONOMOUS REVENUE RECOVERY INTERACTIVE CONTROL CENTER   ")
    print("=" * 80)
    print(f"  * Web Application URL : http://{args.host}:{args.port}")
    print(f"  * Interactive API Docs: http://{args.host}:{args.port}/docs")
    print(f"  * Health Check URL    : http://{args.host}:{args.port}/api/health")
    print(f"  * Environment         : {APP_CONFIG.mode}")
    print("=" * 80 + "\n")

    uvicorn.run(
        "server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=APP_CONFIG.log_level.lower()
    )


if __name__ == "__main__":
    main()
