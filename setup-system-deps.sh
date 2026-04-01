#!/bin/bash
# Neganuki – system-level dependency installer
# Installs non-Poetry dependencies required to run the film scanner on a
# Raspberry Pi 3B running Debian Trixie (or any Debian/Ubuntu derivative).
#
# Run once before `poetry install`:
#   chmod +x setup-system-deps.sh && ./setup-system-deps.sh

set -e

# ── helpers ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        err "This script must be run as root (use sudo)."
        exit 1
    fi
}

# ── main ─────────────────────────────────────────────────────────────────────
echo "Neganuki – system dependency setup"
echo "==================================="

require_root

echo ""
echo "Updating package lists..."
apt-get update -qq

# ── 1. Poetry ─────────────────────────────────────────────────────────────────
echo ""
echo "[1/3] Poetry"
if command -v poetry &>/dev/null; then
    ok "Poetry already installed ($(poetry --version))"
else
    warn "Poetry not found – installing via the official installer..."
    # Install as the sudo-invoking user, not root
    REAL_USER="${SUDO_USER:-$USER}"
    sudo -u "$REAL_USER" bash -c \
        'curl -sSL https://install.python-poetry.org | python3 -'
    ok "Poetry installed. Make sure ~/.local/bin is on your PATH."
fi

# ── 2. libcamera / picamera2 system packages ──────────────────────────────────
echo ""
echo "[2/3] libcamera and picamera2 system packages"
CAMERA_PKGS=(
    libcamera-dev          # libcamera C headers + pkg-config
    libcamera-tools        # cam, qcam – useful for testing
    python3-libcamera      # Python bindings built against system libcamera
    python3-picamera2      # picamera2 (system-managed; matches libcamera ABI)
)

MISSING_CAMERA=()
for pkg in "${CAMERA_PKGS[@]}"; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
        ok "$pkg already installed"
    else
        MISSING_CAMERA+=("$pkg")
    fi
done

if [[ ${#MISSING_CAMERA[@]} -gt 0 ]]; then
    echo "Installing: ${MISSING_CAMERA[*]}"
    apt-get install -y "${MISSING_CAMERA[@]}"
    ok "Camera packages installed"
else
    ok "All camera packages already present"
fi

# ── 3. lgpio Python package via Debian (required by rpi-lgpio / RPi.GPIO) ────
# Using python3-lgpio from apt avoids compiling the C extension inside the venv.
# Poetry is then configured to inherit system site-packages so rpi-lgpio can
# find lgpio at runtime.
echo ""
echo "[3/4] lgpio (required by rpi-lgpio / RPi.GPIO)"
LGPIO_PKGS=(
    python3-lgpio          # lgpio Python bindings (Debian-built, no compilation)
    liblgpio1              # Runtime shared library needed by python3-lgpio
)

MISSING_LGPIO=()
for pkg in "${LGPIO_PKGS[@]}"; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
        ok "$pkg already installed"
    else
        MISSING_LGPIO+=("$pkg")
    fi
done

if [[ ${#MISSING_LGPIO[@]} -gt 0 ]]; then
    echo "Installing: ${MISSING_LGPIO[*]}"
    apt-get install -y "${MISSING_LGPIO[@]}"
    ok "lgpio packages installed"
else
    ok "All lgpio packages already present"
fi

# ── 4. Configure Poetry venv to inherit system site-packages ─────────────────
# This lets the Poetry venv see python3-lgpio (and python3-picamera2) that were
# installed by apt without bundling them as pip packages.
echo ""
echo "[4/4] Poetry venv configuration"
REAL_USER="${SUDO_USER:-$USER}"
PROJECT_DIR="$(dirname "$(realpath "$0")")"  

# Enable system-site-packages for this project's venv only (local config).
sudo -u "$REAL_USER" bash -c \
    "cd \"$PROJECT_DIR\" && poetry config virtualenvs.options.system-site-packages true --local"
ok "Poetry venv configured to use system site-packages"

# Recreate the venv so the flag takes effect immediately.
if sudo -u "$REAL_USER" bash -c "cd \"$PROJECT_DIR\" && poetry env info --path" &>/dev/null; then
    warn "Removing existing venv so system-site-packages flag takes effect..."
    sudo -u "$REAL_USER" bash -c "cd \"$PROJECT_DIR\" && poetry env remove --all"
    ok "Old venv removed"
fi

# ── done ──────────────────────────────────────────────────────────────────────
echo ""
echo "==================================="
ok "System dependencies ready."
echo ""
echo "Next step – install Python dependencies with Poetry:"
echo "  poetry install"
echo "  # or, to include the optional camera extras:"
echo "  poetry install --extras camera"
