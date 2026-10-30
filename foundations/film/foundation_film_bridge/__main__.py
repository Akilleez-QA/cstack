"""Run with python -B -m foundation_film_bridge from foundations/film."""
import sys

# Do not create bytecode caches during ordinary invocation.
sys.dont_write_bytecode = True
from .server import main

raise SystemExit(main())
