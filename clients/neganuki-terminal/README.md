# Neganuki Terminal Client

A terminal-based client suite for controlling the scanner over gRPC from a local shell or over SSH.

## What This Client Can Do

- Start, pause, and resume scans
- Capture single RGB or RAW frames
- Poll and stream scanner status
- Move motor manually
- Manage camera presets
- Set camera controls directly
- Save preview stream frames to disk
- Copy captured files to your SSH client host using scp

## Files

- `scanner_client.py`: Main CLI + reusable Python client class
- `interactive_scanner.py`: Menu-driven interactive terminal UI
- `simple_scan.py`: Lightweight script for quick operations

## Requirements

- Scanner gRPC server running (default: `localhost:50051`)
- Project dependencies installed in your Python environment
- `scp` installed on the machine where this client runs (for copy features)

## Quick Start

Run from the repository root:

```bash
# Full scan
poetry run python clients/neganuki-terminal/scanner_client.py --action scan

# Capture RGB frame
poetry run python clients/neganuki-terminal/scanner_client.py --action capture

# Capture RAW frame
poetry run python clients/neganuki-terminal/scanner_client.py --action capture --raw

# Get scanner status
poetry run python clients/neganuki-terminal/scanner_client.py --action status
```

## SSH Copy Workflow

When this client is executed over SSH, it can auto-detect your SSH client host from `SSH_CONNECTION` or `SSH_CLIENT`.

### Capture and copy automatically

```bash
poetry run python clients/neganuki-terminal/scanner_client.py \
  --action capture \
  --copy-to-host \
  --copy-path ~/scanner-captures
```

### Capture and copy to explicit host/user

```bash
poetry run python clients/neganuki-terminal/scanner_client.py \
  --action capture \
  --copy-to-host \
  --copy-host 192.168.1.20 \
  --copy-user your_user \
  --copy-path ~/scanner-captures
```

### Copy an already captured file

```bash
poetry run python clients/neganuki-terminal/scanner_client.py \
  --action copy \
  --path output/capture_123.png \
  --copy-path ~/scanner-captures
```

## scanner_client.py

Base command:

```bash
poetry run python clients/neganuki-terminal/scanner_client.py --action <action> [flags]
```

### Actions

- `scan`: Start full scan and wait for completion
- `status`: Get current scanner status
- `capture`: Capture one frame (`--raw` enables RAW mode)
- `stream`: Stream status updates
- `test`: Run test flow (start, pause, resume, wait)
- `move-motor`: Manual motor movement (`--steps` required)
- `calc-gains`: Calculate white-balance gains
- `preset-get`: Show active preset + effective controls
- `preset-list`: List available presets
- `preset-set`: Activate preset (`--preset-name` required)
- `preset-create`: Create preset (`--preset-name` + at least one control via flags or `--controls`)
- `set-controls`: Apply direct control values
- `preview`: Save preview stream frames as JPEG
- `copy`: Copy an existing file with `scp` (`--path` required)

### Complete Flag Reference

#### Connection

- `--host` (string, default: `localhost`)
  - Scanner host address
- `--port` (int, default: `50051`)
  - Scanner gRPC port

#### Core action selection

- `--action` (enum, default: `scan`)
  - Allowed values:
    - `scan`
    - `status`
    - `capture`
    - `stream`
    - `test`
    - `move-motor`
    - `calc-gains`
    - `preset-get`
    - `preset-list`
    - `preset-set`
    - `preset-create`
    - `set-controls`
    - `preview`
    - `copy`

#### Capture and copy

- `--raw` (flag)
  - Capture RAW frame (used with `--action capture`)
- `--copy-to-host` (flag)
  - After capture, copy the resulting file via `scp`
- `--copy-path` (string, default: `.`)
  - Remote destination path for `scp`
- `--copy-user` (string, optional)
  - Remote username for `scp`
- `--copy-host` (string, optional)
  - Remote host for `scp`; if omitted, host auto-detection is attempted
- `--path` (string, optional)
  - Local source path for `--action copy` (required for that action)

#### Motor control

- `--steps` (int, optional)
  - Required for `--action move-motor`
  - Positive = forward, negative = backward

#### Presets and controls input

- `--preset-name` (string, optional)
  - Required for `--action preset-set` and `--action preset-create`
- `--controls` (string, default: empty)
  - Comma-separated `key=value` list
  - Example: `exposure_time=9000,brightness=0.1,contrast=1.1`
  - Used by `preset-create`, and also merged into `set-controls`

#### Direct camera controls

- `--ae-enable` (int: `0` or `1`, optional)
- `--exposure-time` (int, optional)
- `--awb-enable` (int: `0` or `1`, optional)
- `--r-gain` (float, optional)
- `--b-gain` (float, optional)
- `--brightness` (float, optional)
- `--contrast` (float, optional)
- `--sharpness` (float, optional)
- `--saturation` (float, optional)

Preset note:
- Every preset parameter can be passed as dedicated flags (`--exposure-time`, `--brightness`, `--contrast`, etc.) when using `--action preset-create`.
- You can also mix dedicated flags and `--controls`; explicit flags and parsed values are merged into the preset payload.

#### Preview streaming

- `--fps` (int, default: `10`)
  - Requested preview stream FPS
- `--quality` (int, default: `75`)
  - JPEG quality for preview stream
- `--preview-dir` (string, default: `output/preview`)
  - Directory where preview frames are saved
- `--max-frames` (int, default: `0`)
  - Stop after N frames (`0` means unlimited)

## scanner_client.py Examples

```bash
# Move motor 200 steps forward
poetry run python clients/neganuki-terminal/scanner_client.py --action move-motor --steps 200

# List camera presets
poetry run python clients/neganuki-terminal/scanner_client.py --action preset-list

# Activate preset
poetry run python clients/neganuki-terminal/scanner_client.py --action preset-set --preset-name neg

# Create preset
poetry run python clients/neganuki-terminal/scanner_client.py \
  --action preset-create \
  --preset-name custom \
  --exposure-time 9000 \
  --brightness 0.1 \
  --contrast 1.1

# Create preset using mixed input (flags + --controls)
poetry run python clients/neganuki-terminal/scanner_client.py \
  --action preset-create \
  --preset-name mixed \
  --exposure-time 9000 \
  --controls "sharpness=1.2,saturation=0.1"

# Set direct controls
poetry run python clients/neganuki-terminal/scanner_client.py \
  --action set-controls \
  --exposure-time 9000 \
  --brightness 0.1 \
  --contrast 1.1

# Save first 50 preview frames
poetry run python clients/neganuki-terminal/scanner_client.py \
  --action preview \
  --fps 10 \
  --quality 75 \
  --preview-dir output/preview \
  --max-frames 50

# Connect to a remote scanner and save preview frames
poetry run python clients/neganuki-terminal/scanner_client.py \
  --host 192.168.1.100 \
  --port 50051 \
  --action preview \
  --fps 10 \
  --quality 75 \
  --preview-dir output/preview_remote \
  --max-frames 100
```

## interactive_scanner.py

Launch:

```bash
poetry run python clients/neganuki-terminal/interactive_scanner.py
```

This menu-based mode prompts for host and port at startup, then exposes these actions:

1. Start Full Scan
2. Get Status
3. Pause Scan
4. Resume Scan
5. Capture Single Frame (RGB)
6. Capture Single Frame (RAW)
7. Stream Status Updates
8. Shutdown Scanner
9. Reconnect
0. Exit

After RGB/RAW capture, it can optionally copy the result to your SSH client host.

## simple_scan.py

Base command:

```bash
poetry run python clients/neganuki-terminal/simple_scan.py [flags]
```

### Complete Flag Reference

- `--host` (string, default: `localhost`)
  - Scanner host
- `--port` (int, default: `50051`)
  - Scanner port
- `--test` (flag)
  - Capture a single test frame instead of full scan
- `--raw` (flag)
  - Use RAW test capture (valid with `--test`)
- `--monitor` (flag)
  - Monitor ongoing scan with status stream

### Examples

```bash
# Quick full scan
poetry run python clients/neganuki-terminal/simple_scan.py

# Test RGB frame capture
poetry run python clients/neganuki-terminal/simple_scan.py --test

# Test RAW frame capture
poetry run python clients/neganuki-terminal/simple_scan.py --test --raw

# Monitor status stream
poetry run python clients/neganuki-terminal/simple_scan.py --monitor
```

## Troubleshooting

- Connection fails:
  - Check scanner server is running
  - Verify `--host` and `--port`

- Copy fails:
  - Ensure `scp` is installed
  - Use `--copy-host` if auto-detection fails
  - Verify SSH keys/permissions for destination host

- Control actions fail:
  - Check scanner state with `--action status`
  - Some actions require idle state on the server side
