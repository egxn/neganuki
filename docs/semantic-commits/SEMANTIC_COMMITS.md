# Semantic Commits - Complete Guide

Complete documentation for semantic commits in the Neganuki project.

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Setup Guide](#setup-guide)
3. [Usage Guide](#usage-guide)
4. [Configuration Summary](#configuration-summary)
5. [Practical Examples](#practical-examples)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Resources](#resources)

---

## Quick Reference

### Commit Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Commit Types

| Type | Use For | Version Bump | Example |
|------|---------|--------------|---------|
| `feat` | New feature | MINOR | `feat(ui): add live preview` |
| `fix` | Bug fix | PATCH | `fix(camera): prevent memory leak` |
| `docs` | Documentation | - | `docs: update README` |
| `style` | Formatting | - | `style: format with black` |
| `refactor` | Code refactor | - | `refactor: simplify controller` |
| `perf` | Performance | PATCH | `perf(camera): optimize capture` |
| `test` | Tests | - | `test: add unit tests` |
| `build` | Build/deps | - | `build: update dependencies` |
| `ci` | CI/CD changes | - | `ci: add GitHub Actions` |
| `chore` | Maintenance | - | `chore: update .gitignore` |
| `revert` | Revert commit | - | `revert: undo feature X` |

### Scopes

Common scopes for this project:
- `camera` - Camera module (IMX477)
- `motor` - Motor control (stepper)
- `fsm` - Finite state machine
- `grpc` - gRPC server/client
- `pipeline` - Scanning pipeline
- `ui` - GUI client (Tkinter)
- `client` - CLI clients
- `deps` - Dependencies
- `docs` - Documentation

### Version Bumping

| Commit Type | Version Change | Example |
|-------------|----------------|---------|
| `fix` | 0.1.0 → 0.1.1 | PATCH |
| `feat` | 0.1.0 → 0.2.0 | MINOR |
| `BREAKING CHANGE` | 0.1.0 → 1.0.0 | MAJOR |

### Common Commands

```bash
# Interactive commit (recommended)
poetry run cz commit

# Manual commit
git commit -m "feat(camera): add live preview"

# Version bump
poetry run cz bump

# Specific version bump
poetry run cz bump --increment PATCH
poetry run cz bump --increment MINOR
poetry run cz bump --increment MAJOR

# Preview version bump
poetry run cz bump --dry-run

# Run pre-commit on all files
poetry run pre-commit run --all-files
```

### Subject Line Rules

- ✅ Use imperative mood: "add" not "added"
- ✅ Use lowercase: "add feature" not "Add feature"
- ✅ No period at end: "add feature" not "add feature."
- ✅ Keep under 50 characters
- ✅ Be specific: "add X" not "update code"

### Footer Format

```bash
# Close single issue
Closes #42

# Close multiple issues
Closes #42, #43, #44

# Reference without closing
Refs #42

# Breaking change
BREAKING CHANGE: explain what breaks and how to migrate
```

---

## Setup Guide

### Prerequisites

- Poetry installed
- Git initialized repository
- Python 3.8+

### Quick Setup

#### Option 1: Automated Setup (Recommended)

```bash
./setup-semantic-commits.sh
```

This script will:
1. Install all dev dependencies
2. Install pre-commit hooks
3. Configure git commit template
4. Run initial formatting checks

#### Option 2: Manual Setup

**1. Install Development Dependencies**

```bash
poetry install --with dev
```

This installs:
- `commitizen ^3.13.0` - Interactive commit helper
- `pre-commit ^3.6.0` - Git hooks framework
- `black ^23.12.0` - Code formatter
- `isort ^5.13.0` - Import sorter
- `flake8 ^7.0.0` - Linter

**2. Install Pre-commit Hooks**

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

This enables:
- Code formatting checks before commits
- Commit message validation
- Common file checks (trailing whitespace, large files, etc.)

**3. Configure Git Commit Template (Optional)**

```bash
git config --local commit.template .gitmessage
```

Provides helpful template when writing commit messages.

### Verification

Check that everything is working:

```bash
# Check commitizen
poetry run cz version

# Check pre-commit
poetry run pre-commit run --all-files

# Try making a test commit
git add .
poetry run cz commit
```

---

## Usage Guide

### Making Commits

#### Interactive Method (Recommended)

```bash
git add .
poetry run cz commit
```

You'll be prompted for:
1. **Type** - Select from list (feat, fix, docs, etc.)
2. **Scope** - Optional component (camera, motor, ui, etc.)
3. **Subject** - Short description (imperative mood)
4. **Body** - Optional detailed explanation
5. **Breaking change** - Yes/No
6. **Footer** - Optional issue references

Example interactive session:
```
? Select the type of change you are committing: feat
? What is the scope of this change? camera
? Write a short and imperative summary: add live preview streaming
? Provide additional contextual information: 
Implemented StreamPreview RPC for real-time camera feed.
Only available when scanner is in idle state.

- Added get_preview_stream_frame() method
- JPEG encoding with configurable quality
- Rate limiting to maintain consistent FPS

? Is this a BREAKING CHANGE? No
? Footer (issues closed, etc.): Closes #42
```

Result:
```
feat(camera): add live preview streaming

Implemented StreamPreview RPC for real-time camera feed.
Only available when scanner is in idle state.

- Added get_preview_stream_frame() method
- JPEG encoding with configurable quality
- Rate limiting to maintain consistent FPS

Closes #42
```

#### Manual Method

```bash
git add .
git commit -m "feat(camera): add live preview streaming"
```

The pre-commit hook will validate format automatically.

For multi-line commits:
```bash
git commit -m "feat(camera): add live preview streaming" \
  -m "" \
  -m "Implemented StreamPreview RPC for real-time feed." \
  -m "" \
  -m "Closes #42"
```

#### Skip Validation (Emergency Only)

```bash
git commit --no-verify -m "emergency fix"
```

⚠️ **Not recommended** - Use only for critical hotfixes.

### Version Management

#### Automatic Version Bump

```bash
poetry run cz bump
```

This will:
1. Read all commits since last version tag
2. Determine appropriate version bump:
   - `feat` → MINOR (0.1.0 → 0.2.0)
   - `fix` → PATCH (0.1.0 → 0.1.1)
   - `BREAKING CHANGE` → MAJOR (0.1.0 → 1.0.0)
3. Update `pyproject.toml` version
4. Generate/update `CHANGELOG.md`
5. Create git tag (e.g., `v0.2.0`)
6. Commit changes

#### Manual Version Bump

```bash
# Specific increment
poetry run cz bump --increment PATCH  # 0.1.0 → 0.1.1
poetry run cz bump --increment MINOR  # 0.1.0 → 0.2.0
poetry run cz bump --increment MAJOR  # 0.1.0 → 1.0.0
```

#### Preview Version Bump

```bash
poetry run cz bump --dry-run
```

Shows what would happen without making changes.

#### Push with Tags

```bash
git push --follow-tags origin main
```

### Pre-commit Hooks

#### What Gets Checked

When you run `git commit`, pre-commit automatically runs:

**1. Code Formatting**
- Black (line length: 100)
- isort (import sorting)
- flake8 (linting)

**2. File Checks**
- Trim trailing whitespace
- Ensure files end with newline
- Validate YAML syntax
- Prevent large files (>5MB)
- Detect merge conflicts
- Check for case conflicts

**3. Commit Message**
- Validate Conventional Commits format
- Check type, scope, subject
- Enforce max length (100 chars)

#### Manual Pre-commit Runs

```bash
# Run on all files
poetry run pre-commit run --all-files

# Run specific hook
poetry run pre-commit run black --all-files
poetry run pre-commit run commitizen --all-files
poetry run pre-commit run flake8 --all-files

# Update hooks to latest versions
poetry run pre-commit autoupdate
```

### Changelog

#### Automatic Generation

Generated automatically when running `cz bump`.

#### Manual Generation

```bash
poetry run cz changelog
```

Creates/updates `CHANGELOG.md` with commits grouped by type:

```markdown
## v0.2.0 (2024-01-15)

### Features
- **camera**: add live preview streaming support (#42)
- **ui**: add pause/resume controls (#45)

### Bug Fixes
- **motor**: resolve GPIO cleanup on error (#38)
- **grpc**: validate connection before streaming (#39)

### Documentation
- add semantic commits setup guide
- update README with client UI instructions
```

---

## Configuration Summary

### Files Created

#### Configuration Files
- ✅ `.commitlintrc.json` - Commit message validation
- ✅ `.czrc` - Commitizen configuration
- ✅ `.gitmessage` - Git commit template
- ✅ `.pre-commit-config.yaml` - Pre-commit hooks
- ✅ `pyproject.toml` - Tool configurations

#### Documentation
- ✅ `CONTRIBUTING.md` - Contribution guidelines
- ✅ `CHANGELOG.md` - Version history
- ✅ `docs/semantic-commits/` - Complete documentation

#### Scripts
- ✅ `setup-semantic-commits.sh` - Automated setup

#### GitHub Templates
- ✅ `.github/ISSUE_TEMPLATE/bug_report.yml`
- ✅ `.github/ISSUE_TEMPLATE/feature_request.yml`
- ✅ `.github/PULL_REQUEST_TEMPLATE.md`

### Tool Configuration

#### Commitizen (`pyproject.toml`)

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version = "0.1.0"
tag_format = "v$version"
version_files = ["pyproject.toml:version"]
update_changelog_on_bump = true
```

#### Black (`pyproject.toml`)

```toml
[tool.black]
line-length = 100
target-version = ['py38', 'py39', 'py310']
```

#### isort (`pyproject.toml`)

```toml
[tool.isort]
profile = "black"
line_length = 100
```

#### flake8 (`pyproject.toml`)

```toml
[tool.flake8]
max-line-length = 100
extend-ignore = "E203, W503"
```

### Pre-commit Hooks

```yaml
repos:
  - repo: https://github.com/commitizen-tools/commitizen
    hooks:
      - id: commitizen
  
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    hooks:
      - id: flake8
  
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

---

## Practical Examples

### Features (feat)

#### Camera Module

```bash
feat(camera): add live preview streaming support

Implemented StreamPreview RPC for real-time camera feed.
Only available when scanner is in idle state.

- Added get_preview_stream_frame() method
- JPEG encoding with configurable quality (1-100)
- Rate limiting to maintain consistent FPS (1-30)
- Automatic RGB to BGR conversion for OpenCV

Technical details:
- Preview uses existing Picamera2 instance
- No camera restart required
- Memory efficient (frames not stored)

Closes #42
```

```bash
feat(camera): add RAW capture with DNG export

Extended camera module to support RAW Bayer capture
with optional DNG file export.

- Added capture_raw() method
- Support for 16-bit Bayer data
- Optional tifffile/rawpy for DNG export
- Automatic mode switching (preview ↔ raw)

Closes #28
```

#### Motor Control

```bash
feat(motor): implement position tracking

Added absolute position tracking to stepper motor.

- Track total steps since initialization
- get_position() returns current position
- reset_position() for manual recalibration
- Position preserved across hold/release

Useful for resuming interrupted scans.

Closes #35
```

#### State Machine

```bash
feat(fsm): add pause and resume states

Extended FSM with pause/resume capability for
mid-scan interruption and continuation.

States added:
- paused: Scan temporarily stopped
- Transitions: pause, resume

Integration:
- Pipeline controller pause_scan() method
- gRPC PauseScan/ResumeScan RPCs
- Motor holds position during pause

Closes #31
```

#### User Interface

```bash
feat(ui): create Tkinter GUI client

Implemented graphical user interface for scanner control.

Features:
- Connection management with host/port config
- Scan controls (start, pause, resume, stop)
- Frame capture (RGB/RAW)
- Live preview display with auto-scaling
- Status monitoring with auto-refresh
- Scrollable log with color-coded messages

Located in: client/neganuki-ui/scanner_gui.py

Closes #40
```

#### gRPC API

```bash
feat(grpc): add server streaming for status updates

Implemented StreamStatus RPC for real-time status monitoring.

- Server-side streaming (yields StateUpdate messages)
- Poll interval: 500ms
- Streams until client cancels
- Includes state, frame_count, and message

Allows clients to monitor scan progress without polling.

Closes #33
```

### Bug Fixes (fix)

#### Camera

```bash
fix(camera): prevent memory leak in continuous capture

Fixed memory leak caused by creating new Picamera2 instance
on each capture.

Root cause:
- capture_frame() was calling reconfigure()
- reconfigure() stopped/restarted camera
- Resources not properly released

Solution:
- Single Picamera2 instance in __init__
- Reuse instance for all captures
- Only reconfigure when mode changes

Memory usage reduced from ~500MB/hour to stable ~50MB.

Fixes #38
```

```bash
fix(camera): synchronize frame and metadata capture

Fixed race condition where metadata didn't match captured frame.

Issue:
- capture_array() and get_metadata() called separately
- Metadata could be from next frame

Solution:
- Use capture_request() for atomic capture
- Extract both frame and metadata from single request
- Ensures frame and metadata are synchronized

Fixes #44
```

#### Motor Control

```bash
fix(motor): cleanup GPIO pins on exception

Fixed GPIO pins remaining in use after motor errors.

Issue:
- Exception during step sequence
- GPIO pins not released
- "Pin already in use" on next run

Solution:
- try/finally block in step methods
- cleanup() called in __del__
- Added reinitialize() for recovery

Fixes #29
```

#### Pipeline

```bash
fix(pipeline): handle empty frame list in stitcher

Fixed IndexError when stitching with no frames.

Root cause:
- stitcher.stitch([]) called with empty list
- No validation before accessing frames[0]

Solution:
- Check len(frames) > 0
- Return None if empty
- Log warning message

Prevents crash during error recovery.

Fixes #52
```

#### gRPC

```bash
fix(grpc): validate connection before streaming

Fixed server crash when client disconnects during preview stream.

Issue:
- StreamPreview continued after client disconnect
- BrokenPipe exception not caught
- Server thread crashed

Solution:
- Check context.is_active() in loop
- Catch exceptions in stream handler
- Graceful cleanup on disconnect

Fixes #47
```

### Documentation (docs)

```bash
docs: add live preview implementation guide

Created comprehensive documentation for live preview feature.

Contents:
- Protocol buffer definitions
- Camera streaming method
- Server implementation
- Client integration
- Performance metrics
- Configuration options
- Troubleshooting guide

File: LIVE_PREVIEW_IMPLEMENTATION.md
```

```bash
docs: update README with client UI instructions

Added section explaining how to run all client interfaces.

Sections added:
- GUI client (Tkinter)
- Interactive menu client
- Simple automation scripts
- Programmatic client library

Includes installation steps and quick start examples.
```

```bash
docs(contributing): add semantic commit examples

Extended CONTRIBUTING.md with real-world commit examples
for all commit types and scopes.

Makes it easier for new contributors to write
properly formatted commit messages.
```

### Refactoring (refactor)

```bash
refactor(camera): extract JPEG encoding to helper

Moved JPEG encoding logic to separate method for reusability.

Changes:
- Created _encode_jpeg(frame, quality) helper
- Used in both capture_frame() and StreamPreview()
- Consistent encoding parameters
- Easier to test

No functional changes.
```

```bash
refactor(fsm): use YAML for state configuration

Replaced hardcoded state definitions with YAML configuration.

Benefits:
- States and transitions in states.yaml
- Easy to modify without code changes
- Better documentation of state machine
- Supports comments for complex transitions

Backward compatible with existing code.
```

```bash
refactor(pipeline): simplify controller initialization

Reduced controller initialization complexity by using
dataclasses for configuration.

Changes:
- CameraConfig dataclass
- MotorConfig dataclass
- EvaluatorConfig dataclass
- Default values in dataclass definitions

Cleaner API, better type hints, easier testing.
```

### Performance (perf)

```bash
perf(camera): optimize frame capture for streaming

Reduced frame capture time by 40% for streaming.

Optimizations:
- Reuse capture_array() buffer
- Skip unnecessary format conversions
- Cache configuration settings
- Avoid redundant metadata queries

Streaming now achieves 15 FPS (was 10 FPS) at full resolution.
```

```bash
perf(stitcher): cache feature descriptors

Implemented descriptor caching to speed up stitching.

Before: 2.5s per frame pair
After: 0.8s per frame pair (3x faster)

Approach:
- Compute descriptors once per frame
- Store in frame metadata
- Reuse for all matching operations

Significantly improves scan speed for multi-frame stitching.
```

```bash
perf(grpc): reduce frame encoding overhead

Optimized JPEG encoding in preview stream.

Changes:
- Parallel encoding (ThreadPoolExecutor)
- Adjustable quality per client
- Buffer reuse for encoding
- Reduced memory allocations

Bandwidth usage reduced by 25% without quality loss.
```

### Tests (test)

```bash
test(camera): add unit tests for capture methods

Added comprehensive tests for IMX477Camera class.

Tests cover:
- Initialization with different resolutions
- Preview mode capture
- RAW mode capture
- Mode switching
- Error handling
- Resource cleanup

Coverage: 95% for camera module
```

```bash
test(motor): add position tracking tests

Added tests for stepper motor position tracking.

Test cases:
- Position increases on forward steps
- Position decreases on reverse steps
- Position maintained during hold
- Reset sets position to zero
- Position survives reinitialize

Ensures reliable position tracking for resume feature.
```

### Build & Dependencies (build)

```bash
build: add development dependencies

Added tools for code quality and semantic commits.

Dependencies added:
- commitizen ^3.13.0
- pre-commit ^3.6.0
- black ^23.12.0
- isort ^5.13.0
- flake8 ^7.0.0

Configured in [tool.poetry.group.dev.dependencies]
```

```bash
build(deps): update grpcio to 1.60.0

Updated gRPC dependencies to latest stable version.

Changes:
- grpcio: 1.56.0 → 1.60.0
- grpcio-tools: 1.56.0 → 1.60.0

Includes security fixes and performance improvements.
```

### Chores (chore)

```bash
chore: add pre-commit hooks configuration

Configured pre-commit hooks for code quality.

Hooks added:
- commitizen (commit message validation)
- black (code formatting)
- isort (import sorting)
- flake8 (linting)
- trailing-whitespace
- end-of-file-fixer
- check-yaml

File: .pre-commit-config.yaml
```

```bash
chore: update .gitignore for development files

Extended .gitignore to exclude development artifacts.

Added:
- Pre-commit cache
- Testing artifacts (.pytest_cache, htmlcov)
- IDE files (.vscode, .idea)
- Generated protobuf files
- Output directories

Keeps repository clean.
```

### Style (style)

```bash
style: format codebase with black

Formatted all Python files with Black (line length: 100).

No functional changes, only formatting improvements.
```

```bash
style(grpc): organize imports with isort

Sorted imports in gRPC module according to isort profile.

Order:
1. Standard library
2. Third-party packages
3. Local imports

Improves readability.
```

### CI/CD (ci)

```bash
ci: add GitHub Actions workflow for testing

Implemented CI pipeline for automated testing.

Workflow runs on:
- Push to main
- Pull requests
- Manual trigger

Steps:
- Checkout code
- Install Poetry
- Install dependencies
- Run pytest
- Upload coverage

File: .github/workflows/test.yml
```

### Breaking Changes (BREAKING CHANGE)

```bash
feat(camera)!: change capture_frame return type

BREAKING CHANGE: capture_frame() now returns dict instead of array.

Old behavior:
  frame = camera.capture_frame()  # Returns np.ndarray

New behavior:
  result = camera.capture_frame()  # Returns dict
  frame = result['frame']
  metadata = result['metadata']

Reason:
Provides access to metadata without separate call.

Migration:
Replace `frame = camera.capture_frame()`
with `frame = camera.capture_frame()['frame']`

Affects: All code using camera.capture_frame()
```

### Revert (revert)

```bash
revert: revert "feat(camera): add video recording"

This reverts commit abc123def456.

Reason:
Feature caused memory leaks and conflicts with streaming.
Will reimplement after fixing resource management.

Related: #55
```

### Multi-Type Commits

#### Multiple Fixes

```bash
fix: resolve multiple GPIO and camera issues

Fixed several hardware control issues:

Camera:
- Prevent memory leak in continuous capture
- Synchronize frame and metadata capture

Motor:
- Cleanup GPIO pins on exception
- Fix position tracking after reinitialize

All fixes related to resource management and cleanup.

Fixes #38, #44, #29, #51
```

#### Feature Bundle

```bash
feat(ui): implement complete GUI client

Created full-featured Tkinter GUI for scanner control.

Components:
- Connection management panel
- Scan control buttons (start/pause/resume/stop)
- Frame capture controls (RGB/RAW)
- Live preview canvas with auto-scaling
- Status monitoring with auto-refresh
- Scrollable log with color-coded messages
- Progress indicators

Includes comprehensive documentation and README.

Closes #40, #41, #42
```

---

## Best Practices

### Subject Line Guidelines

#### Good Patterns

- **"add X"** - New functionality
  - `add live preview streaming`
  - `add position tracking`
  
- **"implement X"** - New feature
  - `implement pause/resume states`
  - `implement RAW capture`

- **"fix X"** - Bug fix
  - `fix memory leak in capture`
  - `fix GPIO cleanup on error`

- **"prevent X"** - Defensive fix
  - `prevent crash on disconnect`
  - `prevent duplicate initialization`

- **"optimize X"** - Performance
  - `optimize frame capture speed`
  - `optimize feature matching`

- **"refactor X"** - Code improvement
  - `refactor controller initialization`
  - `refactor JPEG encoding logic`

- **"extract X"** - Code organization
  - `extract JPEG encoding to helper`
  - `extract configuration to dataclass`

- **"update X"** - Modification
  - `update README with instructions`
  - `update dependencies to latest`

- **"remove X"** - Deletion
  - `remove deprecated capture method`
  - `remove unused imports`

#### Keep It Imperative

- ✅ "add feature"
- ❌ "added feature"
- ❌ "adds feature"
- ❌ "adding feature"

#### Good vs Bad Examples

**✅ Good Examples**

```bash
feat(camera): add exposure compensation control
fix(motor): prevent steps when already at position
docs: update API reference with new endpoints
perf(stitcher): optimize feature matching algorithm
test(pipeline): add integration tests for full scan
refactor(fsm): simplify state transitions
chore: update .gitignore for Python artifacts
```

**❌ Bad Examples**

```bash
# Too vague
update code
fix bug
changes

# Missing type
add camera feature

# Wrong tense
added feature
fixed the bug

# Too detailed in subject
feat(camera): add exposure compensation control by implementing new set_exposure_compensation method that takes float value between -2.0 and 2.0

# Multiple unrelated changes
fix camera and motor and update docs

# Not imperative
adds feature
adding new feature
```

### Body Guidelines

#### When to Include Body

Include a body when:
- The change is complex
- The "why" is not obvious
- You want to explain the approach
- Multiple files are affected
- There are migration steps

#### Body Structure

```bash
<type>(<scope>): <subject>

<what changed - high level overview>

<why it changed - motivation and context>

<how it changed - key technical details>

<impact - what this enables or affects>

<footer>
```

#### Body Example

```bash
feat(camera): add live preview streaming

Implemented server-side streaming for real-time camera feed.
Clients can now view live preview while scanner is idle.

Previous approach required polling for individual frames,
which was inefficient and caused UI lag.

New implementation:
- StreamPreview RPC with server streaming
- JPEG encoding with configurable quality
- Rate limiting to maintain consistent FPS
- Automatic stop when scan starts

This enables better user experience for framing and focus
before starting a scan.

Closes #42
```

### Footer Guidelines

#### Issue References

```bash
# Close single issue
Closes #42

# Close multiple issues
Closes #42, #43, #44

# Fix issue
Fixes #42

# Resolve issue
Resolves #42

# Reference without closing
Refs #42
Related: #42
See: #42
```

#### Breaking Changes

```bash
BREAKING CHANGE: explain what breaks and how to migrate

Old:
  result = old_function()

New:
  result = new_function(required_param)

Migration: Add required_param to all calls
```

### Commit Hygiene

#### ✅ Do

- **Commit often**: Small, focused commits
- **One concern per commit**: Don't mix features and fixes
- **Test before committing**: Ensure code works
- **Format before committing**: Let pre-commit handle it
- **Reference issues**: Link to GitHub issues
- **Write for readers**: Clear, complete information
- **Use scope**: Helps navigate history
- **Explain "why"**: Not just "what"

#### ❌ Don't

- **Huge commits**: 50+ files changed
- **Mixed concerns**: Fix bug + add feature + update docs
- **Vague messages**: "update code", "fix stuff"
- **WIP commits**: "work in progress", "temp"
- **Debug commits**: "testing", "trying something"
- **Personal notes**: "remember to fix this later"
- **Obvious statements**: "change code", "update file"

### Workflow Best Practices

#### Feature Development

```bash
# 1. Create feature branch
git checkout -b feat/live-preview

# 2. Make small, focused commits
git add backend/camera/imx477.py
poetry run cz commit
# feat(camera): add get_preview_stream_frame method

git add backend/grpc/scanner.proto
poetry run cz commit
# feat(grpc): add StreamPreview RPC

git add backend/grpc/server.py
poetry run cz commit
# feat(grpc): implement StreamPreview handler

# 3. Push branch
git push origin feat/live-preview

# 4. Create Pull Request
```

#### Bug Fix

```bash
# 1. Create fix branch
git checkout -b fix/memory-leak

# 2. Commit fix with detailed explanation
git add backend/camera/imx477.py
poetry run cz commit
# fix(camera): prevent memory leak in continuous capture

# 3. Add test if applicable
git add tests/test_camera.py
poetry run cz commit
# test(camera): add memory leak regression test

# 4. Push and PR
git push origin fix/memory-leak
```

#### Release Process

```bash
# 1. Ensure on main with latest changes
git checkout main
git pull

# 2. Run tests
poetry run pytest

# 3. Bump version (creates tag and changelog)
poetry run cz bump

# 4. Review changes
git log -1
cat CHANGELOG.md

# 5. Push with tags
git push --follow-tags origin main

# 6. Create GitHub Release
# Manually or with automation
```

---

## Troubleshooting

### Commit Message Issues

#### Issue: Subject may not be empty

```
⧗   input: feat: 
✖   subject may not be empty [subject-empty]
```

**Cause**: Missing subject after type/scope.

**Solution**: Add descriptive subject.

```bash
# Bad
git commit -m "feat: "

# Good
git commit -m "feat(camera): add live preview streaming"
```

#### Issue: Type not allowed

```
⧗   input: update: add feature
✖   type must be one of [feat, fix, docs, ...]
```

**Cause**: Invalid commit type.

**Solution**: Use valid type from allowed list.

```bash
# Bad
git commit -m "update: add feature"

# Good
git commit -m "feat: add feature"
```

#### Issue: Subject too long

```
✖   header must not be longer than 100 characters
```

**Cause**: Subject line exceeds 100 characters.

**Solution**: Shorten subject, move details to body.

```bash
# Bad
git commit -m "feat(camera): add exposure compensation control by implementing new set_exposure_compensation method"

# Good
git commit -m "feat(camera): add exposure compensation control" \
  -m "" \
  -m "Implemented set_exposure_compensation method with range -2.0 to 2.0"
```

### Pre-commit Hook Issues

#### Issue: Black formatting failed

```
black....................................................................Failed
- hook id: black
- files were modified by this hook
```

**Cause**: Code not formatted according to Black style.

**Solution**: Let Black fix formatting, then commit.

```bash
# Fix formatting
poetry run black .

# Stage changes
git add .

# Commit again
git commit
```

#### Issue: isort failed

```
isort....................................................................Failed
```

**Cause**: Imports not sorted correctly.

**Solution**: Run isort, then commit.

```bash
poetry run isort .
git add .
git commit
```

#### Issue: flake8 errors

```
flake8...................................................................Failed
- hook id: flake8
- exit code: 1

./backend/camera/imx477.py:42:80: E501 line too long (105 > 100 characters)
```

**Cause**: Code style issues (line length, unused imports, etc.).

**Solution**: Fix issues manually or with tools.

```bash
# Check issues
poetry run flake8

# Fix line length
# Edit file manually or use black

# Fix unused imports
poetry run isort --remove-redundant-aliases .

# Commit
git add .
git commit
```

#### Issue: Hooks not running

**Cause**: Pre-commit not installed.

**Solution**: Install hooks.

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

#### Issue: Hook installation failed

```
An error has occurred: InvalidConfigError:
```

**Cause**: Invalid `.pre-commit-config.yaml`.

**Solution**: Validate YAML syntax.

```bash
poetry run pre-commit validate-config
```

### Commitizen Issues

#### Issue: Command not found

```
bash: cz: command not found
```

**Cause**: Commitizen not installed or not in PATH.

**Solution**: Install and use through Poetry.

```bash
# Install
poetry install --with dev

# Run through Poetry
poetry run cz commit
```

#### Issue: No commits to bump

```
No commits found to bump version
```

**Cause**: No commits since last version tag, or no version tag exists.

**Solution**: Create initial tag or make commits.

```bash
# Check current version
poetry run cz version

# Create initial tag if none exists
git tag v0.1.0
git push --tags

# Make some commits, then bump
poetry run cz bump
```

#### Issue: Version file not found

```
Unable to find version file
```

**Cause**: `pyproject.toml` missing or version not in specified location.

**Solution**: Ensure `pyproject.toml` has version field.

```toml
[tool.poetry]
version = "0.1.0"
```

### General Issues

#### Issue: Emergency commit needed

**Situation**: Production broken, need to commit without validation.

**Solution**: Use `--no-verify` flag.

```bash
git commit --no-verify -m "emergency: fix production crash"

# Follow up with proper commit message later
git commit --amend
```

#### Issue: Wrong commit message

**Situation**: Committed with wrong message.

**Solution**: Amend commit (if not pushed).

```bash
# Amend last commit
git commit --amend

# Or use commitizen to rewrite
poetry run cz commit --retry
```

#### Issue: Mixed changes committed

**Situation**: Committed multiple unrelated changes in one commit.

**Solution**: Split commit (if not pushed).

```bash
# Reset last commit but keep changes
git reset HEAD~1

# Stage and commit separately
git add backend/camera/
poetry run cz commit
# feat(camera): add feature

git add backend/motor/
poetry run cz commit
# fix(motor): fix bug
```

#### Issue: Need to skip specific hook

**Situation**: One hook failing, need to bypass temporarily.

**Solution**: Use `SKIP` environment variable.

```bash
# Skip specific hook
SKIP=flake8 git commit -m "feat: add feature"

# Skip multiple hooks
SKIP=flake8,black git commit -m "feat: add feature"
```

### Getting Help

#### Check configuration

```bash
# Commitizen config
poetry run cz version
cat .czrc
cat pyproject.toml

# Pre-commit config
poetry run pre-commit --version
cat .pre-commit-config.yaml

# Git config
git config --local --list
```

#### Verify installation

```bash
# Check Poetry environment
poetry env info

# Check installed packages
poetry show

# Check pre-commit hooks
poetry run pre-commit run --all-files
```

#### Debug pre-commit

```bash
# Run with verbose output
poetry run pre-commit run --all-files --verbose

# Run specific hook with debug
poetry run pre-commit run commitizen --verbose --debug
```

---

## Workflow Examples

### Daily Development

```bash
# 1. Start your day
git checkout main
git pull

# 2. Create feature branch
git checkout -b feat/my-feature

# 3. Make changes
# ... edit files ...

# 4. Check formatting (optional, pre-commit does this)
poetry run black .
poetry run isort .
poetry run flake8

# 5. Stage changes
git add .

# 6. Commit with Commitizen
poetry run cz commit

# 7. Continue working
# ... more changes ...
git add .
poetry run cz commit

# 8. Push branch
git push origin feat/my-feature

# 9. Create Pull Request on GitHub
# Use the PR template automatically

# 10. After PR is merged
git checkout main
git pull
git branch -d feat/my-feature
```

### Bug Fix Workflow

```bash
# 1. Create bug fix branch
git checkout -b fix/memory-leak

# 2. Fix the bug
# ... edit backend/camera/imx477.py ...

# 3. Commit fix
git add backend/camera/imx477.py
poetry run cz commit
# Type: fix
# Scope: camera
# Subject: prevent memory leak in continuous capture
# Body: Detailed explanation of fix

# 4. Add test
# ... create test_camera.py ...
git add tests/test_camera.py
poetry run cz commit
# Type: test
# Scope: camera
# Subject: add memory leak regression test

# 5. Push and create PR
git push origin fix/memory-leak

# 6. After merge, delete branch
git checkout main
git pull
git branch -d fix/memory-leak
```

### Release Workflow

```bash
# 1. Ensure you're on main
git checkout main
git pull

# 2. Run full test suite
poetry run pytest
poetry run flake8
poetry run black --check .

# 3. Review commits since last release
git log v0.1.0..HEAD --oneline

# 4. Dry run version bump
poetry run cz bump --dry-run

# 5. Actually bump version
poetry run cz bump

# Example output:
# bump: version 0.1.0 → 0.2.0
# tag to create: v0.2.0
# Updated pyproject.toml
# Updated CHANGELOG.md

# 6. Review changes
git log -1
cat CHANGELOG.md

# 7. Push with tags
git push --follow-tags origin main

# 8. Create GitHub Release (optional)
# Go to GitHub → Releases → Draft new release
# Select tag: v0.2.0
# Use CHANGELOG content for release notes
# Publish release
```

### Hotfix Workflow

```bash
# 1. Create hotfix from main (or latest release tag)
git checkout main  # or: git checkout v0.1.0
git checkout -b hotfix/critical-fix

# 2. Make minimal fix
# ... edit only what's necessary ...

# 3. Commit fix
git add .
poetry run cz commit
# Type: fix
# Breaking change: No
# Subject: fix critical production issue

# 4. Test thoroughly
poetry run pytest

# 5. Push and create PR with "hotfix" label
git push origin hotfix/critical-fix

# 6. After emergency merge, bump patch version
git checkout main
git pull
poetry run cz bump --increment PATCH

# 7. Push hotfix release
git push --follow-tags origin main

# 8. Clean up
git branch -d hotfix/critical-fix
```

### Multi-Contributor Workflow

```bash
# Developer A: Working on feature
git checkout -b feat/preview
# ... commits ...
poetry run cz commit

# Developer B: Working on different feature
git checkout -b feat/controls
# ... commits ...
poetry run cz commit

# Both push their branches
git push origin feat/preview
git push origin feat/controls

# Create separate PRs for review

# After both are approved and merged to main
# Maintainer does release
git checkout main
git pull
poetry run cz bump  # Automatically detects both features
# Version: 0.1.0 → 0.3.0 (two minor bumps)
git push --follow-tags origin main
```

---

## Resources

### Official Documentation

- **[Conventional Commits](https://www.conventionalcommits.org/)** - Standard specification
- **[Commitizen](https://commitizen-tools.github.io/commitizen/)** - Tool documentation
- **[Pre-commit](https://pre-commit.com/)** - Git hooks framework
- **[Semantic Versioning](https://semver.org/)** - Version numbering rules

### Tool Documentation

- **[Black](https://black.readthedocs.io/)** - Python code formatter
- **[isort](https://pycqa.github.io/isort/)** - Python import sorter
- **[flake8](https://flake8.pycqa.org/)** - Python linter
- **[Poetry](https://python-poetry.org/)** - Python dependency management

### Learning Resources

- **[How to Write a Git Commit Message](https://chris.beams.io/posts/git-commit/)** - Best practices
- **[Semantic Commit Messages](https://gist.github.com/joshbuchea/6f47e86d2510bce28f8e7f42ae84c716)** - Quick reference
- **[Angular Commit Guidelines](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)** - Original inspiration

### Project Documentation

- **README.md** - Project overview and setup
- **CONTRIBUTING.md** - Contribution guidelines
- **CHANGELOG.md** - Version history
- **docs/** - Additional documentation

---

## Summary

### Quick Start

```bash
# 1. Setup (one time)
./setup-semantic-commits.sh

# 2. Daily usage
git add .
poetry run cz commit

# 3. Release
poetry run cz bump
git push --follow-tags
```

### Key Points

✅ **Use semantic commits** for clear history and automatic versioning

✅ **Run `poetry run cz commit`** for interactive guided commits

✅ **Pre-commit hooks** automatically enforce code quality

✅ **Version bumping** is automatic based on commit types

✅ **CHANGELOG** is generated automatically

✅ **Reference issues** in footer (Closes #42)

✅ **Write clear subjects** - imperative, specific, under 50 chars

✅ **Add body for complex changes** - explain why and how

✅ **Use scopes** for better navigation (camera, motor, ui, etc.)

### Benefits

🎯 **Clear history** - Understand changes at a glance

🎯 **Automatic versioning** - No manual version management

🎯 **Automatic changelog** - Generated from commits

🎯 **Better collaboration** - Consistent commit format

🎯 **Easier debugging** - Find when features/fixes were added

🎯 **Quality enforcement** - Pre-commit checks before commit

---

**You're all set!** 🚀

For questions or issues:
1. Check [Troubleshooting](#troubleshooting)
2. Review [Examples](#practical-examples)
3. Consult [Resources](#resources)

Happy committing! 🎉
