#!/bin/bash
set -e

echo "=== Post-merge setup ==="

echo "[1/2] Installing Python dependencies..."
pip install -r requirements.txt -q

echo "[2/2] Installing frontend dependencies..."
cd client && npm install --legacy-peer-deps -q

echo "=== Post-merge setup complete ==="
