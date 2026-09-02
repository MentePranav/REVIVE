"""
CLI launcher for the REVIVE Interactive Control Center Web Server.
Usage:
    python -m server.cli --port 8000 --host 127.0.0.1
"""

import argparse
import sys
import uvicorn

# Ensure UTF-8 stdout
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="REVIVE Interactive Control Center Server")
    parser.add_argument("--port", "-p", type=int, default=8000, help="HTTP port to bind (default: 8000)")
    parser.add_argument("--host", "-H", type=str, default="127.0.0.1", help="Network host interface (default: 127.0.0.1)")
    parser.add_argument("--reload", "-r", action="store_true", help="Enable auto-reload on code change")

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("      REVIVE — AUTONOMOUS REVENUE RECOVERY INTERACTIVE CONTROL CENTER   ")
    print("=" * 80)
    print(f"  * Web Application URL : http://{args.host}:{args.port}")
    print(f"  * Interactive API Docs: http://{args.host}:{args.port}/docs")
    print(f"  * Environment         : Local Synthetic Simulation Benchmark")
    print("=" * 80 + "\n")

    uvicorn.run(
        "server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
