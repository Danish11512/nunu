#!/bin/bash
# scripts/scaffold.sh — Create all directories

# SOLID: Separate dirs for models/, interfaces/, utils/ (was flat core/)
mkdir -p backend/{config,core/{models,interfaces},utils,adapters/kalshi,engines/live,strategies,trading,logging,api}
mkdir -p config tests scripts

# Core package (models/, interfaces/, utils/ each have __init__.py below)
touch backend/__init__.py
touch backend/core/__init__.py
touch backend/core/models/__init__.py
touch backend/core/interfaces/__init__.py
touch backend/utils/__init__.py
touch backend/config/__init__.py
touch backend/adapters/__init__.py
touch backend/adapters/kalshi/__init__.py
touch backend/engines/__init__.py
touch backend/engines/live/__init__.py
touch backend/strategies/__init__.py
touch backend/trading/__init__.py
touch backend/logging/__init__.py
touch backend/api/__init__.py
touch tests/__init__.py

# Note: logs/ dir is created at runtime by the logging module
# frontend/ is scaffolded in Phase 8

echo "Scaffold complete. Directories created:"
find backend -type d | sort
find config tests -type d 2>/dev/null | sort
