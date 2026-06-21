import os
import sys
from pathlib import Path

# Add the 'src' directory to sys.path so pytest can find 'mask_core'
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
