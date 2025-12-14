#!/usr/bin/env python3
"""
MyCon Learn Launcher
Double-click this file or run it to start the app.
Press Ctrl+C in the terminal or close the window to stop.
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def main():
    # Get the project directory
    project_dir = Path(__file__).parent

    print("=" * 50)
    print("  MyCon Learn - Vietnamese Practice App")
    print("=" * 50)
    print()
    print("Starting server...")
    print("Press Ctrl+C to stop")
    print()

    # Start uvicorn server
    try:
        process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "app.main:app",
                "--host", "127.0.0.1",
                "--port", "8000",
            ],
            cwd=project_dir,
        )

        # Wait a moment for server to start
        time.sleep(2)

        # Open browser
        url = "http://127.0.0.1:8000"
        print(f"Opening browser at {url}")
        webbrowser.open(url)

        # Wait for process to end (Ctrl+C)
        process.wait()

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        process.terminate()
        process.wait()
        print("Server stopped. Goodbye!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
