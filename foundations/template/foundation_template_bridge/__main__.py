"""Run with python -B -m foundation_template_bridge from foundations/template."""
import sys

# Do not create bytecode caches during ordinary invocation.
sys.dont_write_bytecode = True
from .server import main

raise SystemExit(main())
