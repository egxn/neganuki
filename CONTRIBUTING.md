# Contributing to Neganuki Film Scanner

Thank you for your interest in contributing to Neganuki! This document provides guidelines for contributing to the project.

---

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/your-username/neganuki.git
cd neganuki
```

### 2. Install Dependencies

```bash
poetry install
```

### 3. Install Pre-commit Hooks

```bash
poetry add --group dev commitizen pre-commit black isort flake8
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

---

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code (formatting, etc.)
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes that affect the build system or external dependencies
- **ci**: Changes to CI configuration files and scripts
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

### Scope (optional)

Specify the module or component affected:
- `camera`
- `motor`
- `fsm`
- `grpc`
- `pipeline`
- `ui`
- `client`

For more examples, see [docs/semantic-commits/SEMANTIC_COMMITS_EXAMPLES.md](docs/semantic-commits/SEMANTIC_COMMITS_EXAMPLES.md).

### Examples

#### Feature
```
feat(camera): add live preview streaming support

Implemented StreamPreview RPC for real-time camera feed.
Only available when scanner is in idle state.

- Added get_preview_stream_frame() method
- JPEG encoding with configurable quality
- Rate limiting to maintain consistent FPS

Closes #42
```

#### Bug Fix
```
fix(motor): resolve GPIO cleanup on error

Fixed issue where GPIO pins were not properly cleaned up
when motor encountered an error state.

Fixes #38
```

#### Documentation
```
docs: update README with client UI instructions

Added section explaining how to run the GUI client
and command-line interfaces.
```

#### Refactor
```
refactor(pipeline): simplify frame evaluation logic

Extracted edge detection into separate method for reusability.
No functional changes.
```

---

## Using Commitizen

### Interactive Commit

Instead of `git commit`, use:

```bash
poetry run cz commit
```

This will guide you through creating a properly formatted commit message.

### Bump Version

When ready to release:

```bash
# Automatically bump version based on commits
poetry run cz bump

# Specific version bump
poetry run cz bump --increment PATCH
poetry run cz bump --increment MINOR
poetry run cz bump --increment MAJOR
```

This will:
1. Analyze commits since last tag
2. Determine version bump (MAJOR.MINOR.PATCH)
3. Update version in `pyproject.toml`
4. Create a git tag
5. Generate CHANGELOG.md

---

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-description
```

Branch naming convention:
- `feat/feature-name` - New features
- `fix/bug-description` - Bug fixes
- `docs/what-changed` - Documentation
- `refactor/component-name` - Code refactoring
- `test/test-description` - Test additions/changes

### 2. Make Changes

Write your code following the project's style guidelines:

```bash
# Format code
poetry run black .
poetry run isort .

# Check linting
poetry run flake8 .
```

### 3. Commit Changes

```bash
# Stage changes
git add .

# Commit with Commitizen
poetry run cz commit

# Or manual commit (pre-commit hooks will validate)
git commit
```

### 4. Push and Create PR

```bash
git push origin feat/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Code Style

### Python

We use:
- **Black** for code formatting (line length: 100)
- **isort** for import sorting
- **flake8** for linting

Configuration is in `pyproject.toml` and `.pre-commit-config.yaml`.

### Docstrings

Use Google-style docstrings:

```python
def capture_frame(self, raw: bool = False) -> np.ndarray:
    """Capture a single frame from the camera.
    
    Args:
        raw: If True, capture RAW Bayer data. Default is False (RGB).
    
    Returns:
        NumPy array containing the captured frame.
    
    Raises:
        RuntimeError: If camera is not initialized.
    """
    pass
```

---

## Testing

### Run Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=backend --cov-report=html

# Run specific test file
poetry run pytest tests/test_camera.py
```

### Write Tests

Place tests in the `tests/` directory:

```python
# tests/test_camera.py
import pytest
from backend.camera.imx477 import IMX477Camera

def test_camera_initialization():
    camera = IMX477Camera(resolution=(1920, 1080))
    assert camera.resolution == (1920, 1080)
```

---

## Pull Request Guidelines

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New features have tests
- [ ] Documentation is updated
- [ ] Commit messages follow Conventional Commits
- [ ] Branch is up to date with main

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How has this been tested?

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code where needed
- [ ] I have updated the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing tests pass locally

## Related Issues
Closes #(issue number)
```

---

## Release Process

1. **Ensure all tests pass**
   ```bash
   poetry run pytest
   ```

2. **Bump version with Commitizen**
   ```bash
   poetry run cz bump
   ```

3. **Review generated CHANGELOG**
   ```bash
   cat CHANGELOG.md
   ```

4. **Push with tags**
   ```bash
   git push --follow-tags origin main
   ```

5. **Create GitHub Release**
   - Go to GitHub Releases
   - Select the new tag
   - Copy relevant CHANGELOG section
   - Publish release

---

## Commit Message Examples

### Features
```
feat(ui): add live preview toggle in GUI
feat(grpc): implement StreamPreview RPC
feat(fsm): add pause/resume states
feat(motor): add position tracking
```

### Fixes
```
fix(camera): prevent memory leak in capture loop
fix(pipeline): handle empty frame list in stitcher
fix(grpc): validate connection before streaming
fix(motor): cleanup GPIO on exception
```

### Documentation
```
docs: add live preview implementation guide
docs: update API reference with new RPCs
docs(readme): add client UI instructions
docs(contributing): add commit message examples
```

### Refactoring
```
refactor(camera): extract JPEG encoding to helper
refactor(fsm): use YAML for state configuration
refactor(pipeline): simplify controller initialization
```

### Performance
```
perf(camera): optimize frame capture for streaming
perf(stitcher): cache feature descriptors
perf(grpc): reduce frame encoding overhead
```

### Chores
```
chore: update dependencies to latest versions
chore(deps): bump grpcio to 1.60.0
chore: add pre-commit hooks configuration
build: update Poetry lock file
```

---

## Additional Resources

- [Semantic Commits Guide](docs/semantic-commits/SEMANTIC_COMMITS.md)
- [Quick Reference](docs/semantic-commits/SEMANTIC_COMMITS_QUICKREF.md)
- [Commit Examples](docs/semantic-commits/SEMANTIC_COMMITS_EXAMPLES.md)
- [Setup Guide](docs/semantic-commits/SEMANTIC_COMMITS_SETUP.md)

## Questions?

If you have questions about contributing, please:
1. Check existing issues and discussions
2. Review this document
3. Check the semantic commits documentation
4. Open a new discussion on GitHub

Thank you for contributing! 🎉
