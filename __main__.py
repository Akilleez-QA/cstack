import sys
from pathlib import Path

# Fixed package-local composition path, never controlled by request data.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli import main

raise SystemExit(main())
