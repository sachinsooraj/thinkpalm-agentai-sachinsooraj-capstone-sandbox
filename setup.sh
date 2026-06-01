#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# InfraGPT — One-command setup script
# Usage: bash setup.sh
# ─────────────────────────────────────────────────────────────────────

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  🤖  InfraGPT Setup                             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Check Python 3.10+
python_cmd=""
for cmd in python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c 'import sys; print(sys.version_info >= (3,10))')
        if [ "$version" = "True" ]; then
            python_cmd="$cmd"
            break
        fi
    fi
done

if [ -z "$python_cmd" ]; then
    echo "❌ Python 3.10+ required. Please install it first."
    exit 1
fi

echo "✅ Python: $($python_cmd --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $python_cmd -m venv venv
fi

# Activate
source venv/bin/activate
echo "✅ Virtual environment activated"

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

# Set up .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env created from .env.example"
    echo "   Add your GEMINI_API_KEY for LLM mode."
    echo "   Leave blank to run in deterministic mock mode."
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  🚀  Setup complete! Run:                       ║"
echo "║                                                  ║"
echo "║  Streamlit UI:                                   ║"
echo "║    streamlit run app.py                          ║"
echo "║                                                  ║"
echo "║  CLI:                                            ║"
echo "║    python main.py --scenario pod-crash           ║"
echo "║    python main.py --scenario disk-pressure       ║"
echo "║    python main.py --scenario tf-drift            ║"
echo "║    python main.py --list-scenarios               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
