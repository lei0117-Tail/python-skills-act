# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MultiAgent system with SubAgent delegation for 48%+ token savings
- Comprehensive test suite (13 tests, ≥60% coverage)
- Security module with input sanitization and command validation
- Skill identification caching (saves 200ms + 500 tokens per hit)
- Token usage tracking and statistics API
- Complete API documentation
- Performance optimization features

### Changed
- Updated README with MultiAgent usage examples
- Enhanced build_multi_agent() with new configuration options

### Security
- Input sanitization to prevent prompt injection
- Dangerous command blocking (rm -rf, sudo, etc.)
- Sensitive information redaction (API keys, IPs, emails)
- Concurrent SubAgent limiting

## [0.1.0] - 2024-03-19

### Added
- Initial release
- Basic Agent system with tool calling
- Skills loader for Markdown-based skills
- File operation tools (read, write, edit, list)
- Shell execution tool
- CLI command-line interface
- OpenAI-compatible LLM provider

### Features
- Dynamic skill loading from ~/.claude/skills
- Tool registry for extensible capabilities
- Context builder for system prompts
- Retry logic for transient errors
- Environment variable configuration

[Unreleased]: https://github.com/lei0117-Tail/python-skills-act/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lei0117-Tail/python-skills-act/releases/tag/v0.1.0
