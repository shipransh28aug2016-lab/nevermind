#!/usr/bin/env python3
"""NEVERMIND entry point — python3 run.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentos.server import serve  # noqa: E402

if __name__ == "__main__":
    serve()
