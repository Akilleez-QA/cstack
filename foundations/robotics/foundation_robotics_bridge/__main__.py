import sys

sys.dont_write_bytecode = True
from .server import main

raise SystemExit(main())
