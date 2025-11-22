# Neganuki Documentation

Complete documentation for the Neganuki Film Scanner project.

---

## 📚 Documentation Structure

### 🚀 Getting Started
- **[README.md](../README.md)** - Main project documentation
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Contribution guidelines
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history

### 🔧 Development
- **[semantic-commits/](semantic-commits/)** - Semantic commits setup and guides
  - [Quick Reference](semantic-commits/SEMANTIC_COMMITS_QUICKREF.md)
  - [Full Guide](semantic-commits/SEMANTIC_COMMITS.md)
  - [Examples](semantic-commits/SEMANTIC_COMMITS_EXAMPLES.md)
  - [Setup Summary](semantic-commits/SEMANTIC_COMMITS_SETUP.md)

### 📖 Technical Documentation

Coming soon:
- API Reference
- Architecture Overview
- Hardware Setup Guide
- Troubleshooting Guide

---

## 🔗 Quick Links

### For Users
- [Installation Guide](../README.md#installing-and-using-poetry-to-handle-python-dependencies)
- [Running the Backend](../README.md#running-the-backend)
- [Client UI Guide](../README.md#running-the-client-ui)
- [Hardware Setup](../README.md#hardware-setup)
- [gRPC API](../README.md#grpc-api)

### For Developers
- [Development Setup](../README.md#development-setup)
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Semantic Commits](semantic-commits/)
- [State Machine](../README.md#state-machine)
- [Configuration](../README.md#configuration)

### For Contributors
- [How to Contribute](../CONTRIBUTING.md#getting-started)
- [Commit Message Format](semantic-commits/SEMANTIC_COMMITS.md)
- [Pull Request Guidelines](../CONTRIBUTING.md#pull-request-guidelines)
- [Code Style](../CONTRIBUTING.md#code-style)

---

## 📦 Project Components

### Backend
- **Camera Module** (`backend/camera/`) - IMX477 control with Picamera2
- **Motor Module** (`backend/motor/`) - Stepper motor control (28BYJ-48)
- **FSM Module** (`backend/fsm/`) - State machine with transitions
- **gRPC Module** (`backend/grpc/`) - Server and API definitions
- **Pipeline Module** (`backend/pipeline/`) - Scanning workflow orchestration

### Clients
- **GUI Client** (`client/neganuki-ui/`) - Tkinter graphical interface
- **CLI Clients** (`client/raspberry-pi/`) - Terminal and automation scripts

---

## 🆘 Help & Support

### Common Issues
- [Troubleshooting](../README.md#troubleshooting)
- [GitHub Issues](https://github.com/your-org/neganuki/issues)

### Resources
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Picamera2 Documentation](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)
- [gRPC Documentation](https://grpc.io/docs/)

---

## 📝 License

See [LICENSE](../LICENSE) for details.

---

## 🤝 Contributing

We welcome contributions! Please read our [Contributing Guide](../CONTRIBUTING.md) to get started.

Key points:
1. Use semantic commits
2. Follow code style guidelines
3. Add tests for new features
4. Update documentation

---

## ✨ Quick Commands

```bash
# Install dependencies
poetry install

# Run server
poetry run python backend/grpc/server.py

# Run GUI client
poetry run python client/neganuki-ui/scanner_gui.py

# Make a commit
poetry run cz commit

# Bump version
poetry run cz bump

# Run tests
poetry run pytest
```

---

For more information, explore the documentation links above or check the main [README](../README.md).
