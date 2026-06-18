#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Nunu — Dev runner
#
# Starts the backend (uvicorn) and frontend (Vite) in parallel.
# Auto-installs missing dependencies for both.
#
# Usage:
#   ./run.sh          # Start backend + frontend
#   ./run.sh --help   # Show this message
#   ./run.sh --docker # Also start Docker Compose
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER="${DOCKER:-}"

# ─── Virtual environment ─────────────────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/venv"
if [[ -d "$VENV_DIR" ]]; then
    PYTHON="$VENV_DIR/bin/python"
else
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    PYTHON="$VENV_DIR/bin/python"
    echo "Virtual environment created."
fi

# ─── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker) DOCKER="1"; shift ;;
        --help|-h)
            sed -n '2,10p' "$0"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ─── Cleanup handler ─────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "Shutting down..."
    if [[ -n "${BACKEND_PID:-}" ]]; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    if [[ -n "${FRONTEND_PID:-}" ]]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo "Done."
}
trap cleanup EXIT INT TERM

# ─── Prerequisites check ─────────────────────────────────────────────────────
check_python() {
    if ! command -v python3 &>/dev/null; then
        echo "ERROR: python3 not found." >&2
        exit 1
    fi
}

check_pip_deps() {
    if [[ ! -f "$SCRIPT_DIR/backend/requirements.txt" ]]; then
        echo "WARNING: backend/requirements.txt not found. Skipping pip check." >&2
        return
    fi
    # Quick check — if pydantic isn't installed (Phase 1 dep), install deps
    if ! "$PYTHON" -c "import pydantic" 2>/dev/null; then
        echo "Installing backend dependencies..."
        "$PYTHON" -m pip install -r "$SCRIPT_DIR/backend/requirements.txt"
    fi
}

check_frontend_deps() {
    if [[ ! -d "$SCRIPT_DIR/frontend" ]]; then
        return
    fi
    if [[ ! -f "$SCRIPT_DIR/frontend/node_modules/react/package.json" ]]; then
        echo "Installing frontend dependencies (bun install)..."
        cd "$SCRIPT_DIR/frontend" && bun install
        cd "$SCRIPT_DIR"
    fi
}

# ─── Phase 1: Backend ────────────────────────────────────────────────────────
start_backend() {
    if [[ ! -f "$SCRIPT_DIR/backend/main.py" ]]; then
        echo "INFO: backend/main.py not yet created (Phase 7)."
        echo "      Phase 1 code can be verified with:"
        echo "      $PYTHON -c 'from backend.core.models import Market; print("Phase 1 OK")'"
        return
    fi
    echo "Starting backend (uvicorn)..."
    cd "$SCRIPT_DIR"
    "$PYTHON" -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    echo "Backend running on http://localhost:8000 (PID: $BACKEND_PID)"
}

# ─── Phase 2: Frontend ───────────────────────────────────────────────────────
start_frontend() {
    if [[ ! -d "$SCRIPT_DIR/frontend" ]]; then
        echo "WARNING: frontend/ directory not found. Skipping frontend." >&2
        return
    fi

    if ! command -v bun &>/dev/null; then
        echo "WARNING: bun not found. Skipping frontend." >&2
        return
    fi

    echo "Starting frontend (Vite)..."
    cd "$SCRIPT_DIR/frontend"
    bun run dev --host 0.0.0.0 --port 5173 &
    FRONTEND_PID=$!
    cd "$SCRIPT_DIR"
    echo "Frontend running on http://localhost:5173 (PID: $FRONTEND_PID)"
}

# ─── Phase 3: Docker ─────────────────────────────────────────────────────────
start_docker() {
    if ! command -v docker &>/dev/null; then
        echo "WARNING: docker not found. Skipping Docker." >&2
        return
    fi
    echo "Starting Docker Compose..."
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" up --build -d
}

# ─── Main ────────────────────────────────────────────────────────────────────
echo "═══ Nunu ═══"

check_python
check_pip_deps
check_frontend_deps
start_backend
start_frontend
if [[ -n "$DOCKER" ]]; then
    start_docker
fi

echo ""
echo "Running. Press Ctrl+C to stop."
wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
