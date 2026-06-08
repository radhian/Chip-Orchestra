"""Chip Orchestra backend.

A FastAPI service that implements the Chip Orchestra frontend's task API and
powers it with an agentic RTL-to-GDSII pipeline adapted from GarudaChip
(LangGraph + Ollama -> Verilog -> Icarus simulation -> LibreLane hardening).
"""

__version__ = "0.1.0"
