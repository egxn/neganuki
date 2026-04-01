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

# ── 3. RPi.GPIO via Debian system package ────────────────────────────────────
# python3-rpi.gpio provides `import RPi.GPIO` directly with no lgpio dependency.
# This is the classic, well-tested approach for Raspberry Pi 3B on Debian.
# The Poetry venv inherits it through system-site-packages (step 4).
echo ""
echo "[3/4] RPi.GPIO system package"
GPIO_PKGS=(
    python3-rpi.gpio       # Provides RPi.GPIO, no lgpio required
)

MISSING_GPIO=()
for pkg in "${GPIO_PKGS[@]}"; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
        ok "$pkg already installed"
    else
        MISSING_GPIO+=("$pkg")
    fi
done

if [[ ${#MISSING_GPIO[@]} -gt 0 ]]; then
    echo "Installing: ${MISSING_GPIO[*]}"
    apt-get install -y "${MISSING_GPIO[@]}"
    ok "RPi.GPIO installed"
else
    ok "RPi.GPIO already present"
fi

# Verify the import works in the system Python.
SYS_PYTHON="$(command -v python3)"
if "$SYS_PYTHON" -c "import RPi.GPIO" 2>/dev/null; then
    ok "RPi.GPIO importable in system Python ($SYS_PYTHON)"
else
    err "RPi.GPIO import failed in system Python – check package installation."
    exit 1
fi

# ── 4. Configure Poetry venv to inherit system site-packages ─────────────────
# This lets the Poetry venv see python3-lgpio (and python3-picamera2) that were
# installed by apt without bundling them as pip packages.
echo ""
echo "[4/4] Poetry venv configuration"
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
PROJECT_DIR="$(dirname "$(realpath "$0")")"

# Locate poetry in the real user's PATH (typically ~/.local/bin/poetry).
POETRY_BIN="$(sudo -u "$REAL_USER" bash -lc 'command -v poetry 2>/dev/null')" || true
if [[ -z "$POETRY_BIN" ]]; then
    # Fallback: common install location used by the official installer.
    POETRY_BIN="$REAL_HOME/.local/bin/poetry"
fi
if [[ ! -x "$POETRY_BIN" ]]; then
    err "poetry not found for user '$REAL_USER'. Install it first, then re-run this script."
    exit 1
fi
ok "Using poetry at $POETRY_BIN"

run_poetry() {
    sudo -u "$REAL_USER" bash -c "cd \"$PROJECT_DIR\" && \"$POETRY_BIN\" $*"
}

# 1. Write local config FIRST (creates/updates poetry.toml in the project).
#    This must happen before the venv is created so virtualenv picks up the flag.
run_poetry "config virtualenvs.options.system-site-packages true --local"
ok "poetry.toml updated: virtualenvs.options.system-site-packages = true"

# Verify the flag landed in poetry.toml.
if grep -q "system-site-packages" "$PROJECT_DIR/poetry.toml" 2>/dev/null; then
    ok "Verified poetry.toml contains system-site-packages setting"
else
    err "poetry.toml missing system-site-packages setting – aborting."
    exit 1
fi

# 2. Remove the existing venv AFTER saving the config so the new one inherits it.
warn "Removing existing venv (will be recreated with system-site-packages=true)..."
run_poetry "env remove --all" 2>/dev/null || true
ok "Old venv removed"

# ── 5. Reinstall Poetry dependencies with updated lock ────────────────────────
echo ""
echo "[5/5] Reinstalling Poetry dependencies"
run_poetry "lock"
run_poetry "install"
ok "Poetry environment ready"

# Final sanity check.
if run_poetry "python -c \"import RPi.GPIO; print('RPi.GPIO OK')\"" 2>/dev/null; then
    ok "RPi.GPIO is importable inside the Poetry venv"
else
    err "RPi.GPIO still not importable inside the Poetry venv."
    err "Check that pyvenv.cfg has include-system-site-packages = true:"
    run_poetry "python -c \"import sys; print('\\n'.join(sys.path))\""
    exit 1
fi

# ── done ──────────────────────────────────────────────────────────────────────
echo ""
echo "==================================="
ok "All done. Run the server with:"
echo "  poetry run python backend/grpc/server.py --host 0.0.0.0 --port 50051"
