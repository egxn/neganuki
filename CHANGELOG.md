# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Live preview streaming support in GUI client
- StreamPreview RPC for real-time camera feed
- GUI client with Tkinter for scan control and preview
- Interactive menu client for terminal usage
- Simple automation scripts for scanning
- Pre-commit hooks for code quality
- Semantic commits with Commitizen
- Contributing guidelines

### Changed
- Camera module optimized for continuous streaming
- gRPC server enhanced with preview streaming
- Documentation updated with client usage instructions

### Fixed
- Memory leaks in camera capture loop
- GPIO cleanup on motor errors
- Import paths for generated protobuf files

---

## [0.0.1] - 2025-11-22

### Added
- Initial project structure
- IMX477 camera control module
- 28BYJ-48 stepper motor control
- State machine with transitions
- gRPC server and API definitions
- Pipeline controller for scanning workflow
- Frame quality evaluator
- Image stitching with OpenCV
- Frame cropping utilities
- Poetry dependency management
- Protobuf code generation script
- Basic README documentation

[Unreleased]: https://github.com/egxn/neganuki/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/egxn/neganuki/releases/tag/v0.0.1
