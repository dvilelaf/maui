import sys
import os

# Ensure src is in path if not already (for running as script)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.tui.app import DatabaseMonitor

if __name__ == "__main__":
    app = DatabaseMonitor()
    app.run()
