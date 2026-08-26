"""Server entry point."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from filesystem_mcp.server import app

if __name__ == "__main__":
    app.run()
