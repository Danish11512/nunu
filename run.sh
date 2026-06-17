#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Nunu — Unified dev runner
# 
# Phase 1: Backend only (FastAPI + uvicorn)
# Phase 2: + Frontend (Vite dev server)
# Phase 3: + Docker compose
# Phase 4: + Other services
#
# Usage:
#   ./run.sh                # Start everything (current phase)
#   ./run.sh --phase N      # Set phase explicitly
#   ./run.sh --help         # Show this message
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PHASE="${PHASE:-1}"  # default phase, overridable via env or --phase

# ─── Phase table ─────────────────────────────────────────────────────────────
# Phase | Backend | Frontend | Docker | Notes
#     1 |      ✅ |        ❌ |      ❌ | Python-only, CLI testing
#     2 |      ✅ |        ✅ |      ❌ | Full-stack dev
#     3 |      ✅ |        ✅ |      ✅ | Containerized
# ──────────────────────────────────────────────────────────────────────────────

# ─── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase) PHASE="$2"; shift 2 ;;
        --help|-h)
            sed -n '2,12p' "$0"
            echo ""
            echo "Current phase: $PHASE"
            echo "PHASE can also be set via environment variable."
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
    # Quick check — if uvicorn isn't installed, try to install deps
    if ! python3 -c "import fastapi" 2>/dev/null; then
        echo "Installing backend dependencies..."
        pip3 install -r "$SCRIPT_DIR/backend/requirements.txt"
    fi
}

# ─── Phase 1: Backend ────────────────────────────────────────────────────────
start_backend() {
    echo "Starting backend (uvicorn)..."
    cd "$SCRIPT_DIR/backend"
    python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    cd "$SCRIPT_DIR"
    echo "Backend running on http://localhost:8000 (PID: $BACKEND_PID)"
}

# ─── Phase 2: Frontend ───────────────────────────────────────────────────────
start_frontend() {
    if [[ ! -d "$SCRIPT_DIR/frontend" ]]; then
        echo "WARNING: frontend/ directory not found. Skipping frontend." >&2
        return
    fi

    if ! command -v npm &>/dev/null; then
        echo "WARNING: npm not found. Skipping frontend." >&2
        return
    fi

    if [[ ! -d "$SCRIPT_DIR/frontend/node_modules" ]]; then
        echo "Installing frontend dependencies..."
        cd "$SCRIPT_DIR/frontend" && npm install
        cd "$SCRIPT_DIR"
    fi

    echo "Starting frontend (Vite)..."
    cd "$SCRIPT_DIR/frontend"
    npx vite --host 0.0.0.0 --port 5173 &
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
echo "═══ Nunu — Phase $PHASE ═══"

case "$PHASE" in
    1)
        check_python
        check_pip_deps
        start_backend
        echo ""
        echo "Phase 1 running. Press Ctrl+C to stop."
        wait $BACKEND_PID
        ;;
    2)
        check_python
        check_pip_deps
        start_backend
        start_frontend
        echo ""
        echo "Phase 2 running. Press Ctrl+C to stop."
        wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
        ;;
    3)
        start_docker
        echo "Phase 3 running. Use 'docker compose down' to stop."
        ;;
    *)
        echo "Unknown phase: $PHASE. Valid: 1, 2, 3" >&2
        exit 1
        ;;
esac
