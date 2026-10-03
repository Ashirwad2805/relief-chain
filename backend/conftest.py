import os
import sys

os.environ["PANDAS_USE_PYARROW"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
