#!/bin/bash
# Legal Atlas - Quick Setup Script

set -e

echo "Legal Atlas Setup"
echo "===================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python 3.11+ required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "Python $PYTHON_VERSION detected"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null

# Install dependencies
echo "Installing dependencies..."
pip install -e . > /dev/null

echo ""
echo "Installation complete!"
echo ""
echo "Quick Start:"
echo "   source .venv/bin/activate"
echo "   python -m legal_rag serve"
echo ""
echo "Full documentation: README.md"
echo ""
