"""conftest.py — put golden/ on PYTHONPATH so `from model.x import ...` works."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))