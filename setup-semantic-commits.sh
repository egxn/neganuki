#!/bin/bash

# Neganuki Semantic Commits Setup Script
# This script sets up all necessary tools for semantic commits

set -e

echo "🚀 Setting up Semantic Commits for Neganuki..."
echo ""

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Please install Poetry first:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

echo "✓ Poetry found"

# Install dependencies
echo ""
echo "📦 Installing development dependencies..."
poetry install --with dev

# Install pre-commit hooks
echo ""
echo "🪝 Installing pre-commit hooks..."
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg

# Set git commit template
echo ""
echo "📝 Configuring git commit template..."
git config --local commit.template .gitmessage

# Run pre-commit on all files to ensure everything is formatted
echo ""
echo "🔍 Running pre-commit checks on all files..."
poetry run pre-commit run --all-files || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "📚 Quick Reference:"
echo "   • Make a commit:    poetry run cz commit"
echo "   • Bump version:     poetry run cz bump"
echo "   • Run hooks:        poetry run pre-commit run --all-files"
echo ""
echo "📖 For more details, see:"
echo "   • docs/semantic-commits/"
echo "   • CONTRIBUTING.md"
echo ""
