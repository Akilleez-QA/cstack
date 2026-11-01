"""Run with python -B -m foundation_math_bridge from the source root."""
import sys

# Do not create bytecode caches during backend imports in ordinary invocation.
sys.dont_write_bytecode = True
from .server import main

raise SystemExit(main())
