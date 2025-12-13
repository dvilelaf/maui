import subprocess
import signal
import sys
import time


def run_dev():
    """
    Run both the Telegram Bot and the FastAPI Web App concurrently.
    Handles distinct processes and graceful shutdown.
    """
    print("🚀 Starting Maui Development Environment...")

    # Start FastAPI Web App
    print("🌐 Launching Web App (Uvicorn)...")
    webapp_process = subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-m",
            "uvicorn",
            "src.webapp.app:app",
            "--reload",
            "--host",
            "0.0.0.0",
            "--port",
            "8123",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    # Start Telegram Bot
    print("jq Launching Telegram Bot...")
    bot_process = subprocess.Popen(
        ["uv", "run", "python", "src/main.py"], stdout=sys.stdout, stderr=sys.stderr
    )

    shutdown = False

    def signal_handler(sig, frame):
        nonlocal shutdown
        print("\n🛑 Signal received, shutting down...")
        shutdown = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while not shutdown:
            # Check if processes are alive
            if webapp_process.poll() is not None:
                print("Web App exited unexpectedly.")
                shutdown = True
            if bot_process.poll() is not None:
                print("Bot exited unexpectedly.")
                shutdown = True

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n🛑 KeyboardInterrupt caught...")
        shutdown = True
    finally:
        print("Terminating processes...")

        # Terminate Web App
        if webapp_process.poll() is None:
            webapp_process.terminate()

        # Terminate Bot
        if bot_process.poll() is None:
            bot_process.terminate()

        # Wait for them to exit
        try:
            webapp_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Web App did not exit, killing...")
            webapp_process.kill()

        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Bot did not exit, killing...")
            bot_process.kill()

        print("Done.")


if __name__ == "__main__":
    run_dev()
