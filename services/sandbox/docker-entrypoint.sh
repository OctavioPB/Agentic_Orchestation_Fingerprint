#!/bin/bash
# Selects the correct scenario workspace at container start based on SCENARIO_ID.
# Runs as root during setup, then drops to coder before handing off to code-server.
set -euo pipefail

WORKSPACE_ROOT="/home/coder"
PROJECT_DIR="${WORKSPACE_ROOT}/project"

: "${SCENARIO_ID:=scenario_corrupted_warehouse_v1}"

echo "[entrypoint] SCENARIO_ID=${SCENARIO_ID}"

case "${SCENARIO_ID}" in
  scenario_corrupted_warehouse_v1)
    echo "[entrypoint] activating workspace_v1 (The Corrupted Warehouse)"
    cp -a /opt/orchid/workspace_v1/. "${PROJECT_DIR}/"
    cd "${PROJECT_DIR}" && python3 seed_db.py
    ;;
  scenario_silent_pipeline_v1)
    echo "[entrypoint] activating workspace_v2 (The Silent Pipeline)"
    cp -a /opt/orchid/workspace_v2/. "${PROJECT_DIR}/"
    ;;
  *)
    echo "[entrypoint] ERROR: unknown SCENARIO_ID '${SCENARIO_ID}'" >&2
    exit 1
    ;;
esac

chown -R coder:coder "${PROJECT_DIR}"

echo "[entrypoint] workspace ready — handing off to code-server"
exec sudo --user=coder /usr/bin/entrypoint.sh "$@"
