import sys
import os

# Add the parent directory to sys.path to allow absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prete_py.main import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
