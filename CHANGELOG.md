# Changelog

All notable changes to **PromptBlender** will be documented in this file.

**PromptBlender** is a no-code automation tool that simplifies how you test and optimize prompts for Large Language Models (LLMs). Instead of manually testing prompt variations one by one, PromptBlender automatically generates hundreds or thousands of prompt combinations, executes them against your chosen LLM, and provides comprehensive analysis of the results.

- **Author**: Edans Sandes
- **Current Version**: 0.2.3
- **Repository**: https://github.com/edanssandes/prompt-blender
- **License**: MIT

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- RAG feature implementation
- Zoom functionality to PromptPage
- New status label in the bottom pane

### Changed

- Debounce functionality for prompt text changes to reduce flickering

### Fixed

- Fixed bug where only the first instance of duplicate placeholders was highlighted in prompt editor
- Added error handling when loading analysis modules

## [0.2.3] - 2025-11-14

### Added

- Support for --merge option in GUI mode
- Menu expiration options for error items
- Multiple prompt examples for template loading

### Changed

- Refactored timestamp generation for cross-platform compatibility
- Enhanced cache expiration logic with error filtering support
- Updated menu labels
- Updated english_translation.json example to support multiple prompts

### Fixed

- Character count label background color for transparency
- Error handling in analyse function for null and unknown response formats
- Test adjustments

## [0.2.2] - 2025-11-02

### Added

- Command line execution feature
- --overwrite parameter
- Dump result file parameter
- Cache directory support
- Non-GUI execution awareness
- Test suite for result file operations
- Saving intermediate results

### Changed

- Refactored code (result_file.py creation, menu state management, preferences class)
- Updated screenshots
- New README structure
- Changed from PyPDF2 to pypdf
- Gitignore adjustments
- Updated unittests
- GUI refactoring (move classes, refactor dialogs, etc.)

### Fixed

- Config file existence check
- Progress freezes if canceled during batch load
- Code refactoring at show_batch_warning
- Created no-gui batch confirmation
- Improved error handling in batch execution
- Safety check for destroyed prompt editor

### Removed

- Unused dialogs
- Unused files

## [0.2.1] - 2025-10-02

### Added

- Character count feature in prompt editor
- Drag and drop variables to prompt
- Support for WebSearch tool with response API
- Support for GPT ResponseAPI
- Customized maximum rows in preference setup
- Image loading and processing
- GPT-5 support
- Better support for multiple outputs
- Individual cache expiration

### Changed

- Refactor API key input to use threaded dialog
- Update dependencies in pyproject.toml
- Update model choices - gpt-4o
- Update version numbers

### Fixed

- JSON parsing in exec function
- Menu binding issues
- Ensure at least one row in analysis results

## [0.2.0] - 2025-07-30

### Added

- GUI support and wxPython dependency
- New pbp file format
- Multiple GUI improvements and new features
- Module info attribute in llm plugins
- GUI and CLI sections to README

### Changed

- Major refactoring for GUI configuration
- Update version number
- Adjusting README indentation
- Creating pyproject.toml for pip installation
- README adjustments

### Fixed

- Bug fixes in get_selected_module and get_module_args
- Minor bug fixes to GUI
- Fixing git url

### Removed

- Deleted unused files
