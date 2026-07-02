#!/bin/bash
# Build exiur for Android (Termux)
# Run this inside Termux: bash build-termux.sh

set -e

echo "Installing dependencies..."
pkg update -y
pkg install -y python pyinstaller

echo "Installing project..."
pip install -e ".[build]"

echo "Building..."
python build.py

echo ""
echo "Done! Binary: dist/exiur"
echo "Run: ./dist/exiur"
