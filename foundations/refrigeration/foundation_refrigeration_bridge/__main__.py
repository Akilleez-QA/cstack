"""Run with python -B -m foundation_refrigeration_bridge from foundations/refrigeration."""
import sys

# Do not create bytecode caches during ordinary invocation.
sys.dont_write_bytecode = True
from .server import main

raise SystemExit(main())
