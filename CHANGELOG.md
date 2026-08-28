# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-22

### Added
- FastMCP 3.x compatible server with stdio, SSE, and Streamable HTTP transports
- Bearer token authentication for SSE/HTTP transports (TokenVerifier)
- 6 MCP tools: `read_file`, `write_file`, `list_dir`, `search_files`, `glob`, `patch_file`
- Comprehensive security: sandbox root, symlink protection, file size limits, absolute path control
- Structured logging via structlog with correlation IDs
- Pydantic Settings configuration with env var support (FILESYSTEM_MCP_*)
- Full test coverage (unit + integration, >90%)
- Multi-stage Dockerfile (non-root user, health checks, distroless base)
- GitHub Actions CI/CD: lint, typecheck, test, build, PyPI publish on release
- Keep a Changelog + SemVer 1.0.0

### Changed
- **BREAKING**: Server entry point moved to `filesystem_mcp.server:main` (was `filesystem_mcp:app`)
- **BREAKING**: Tool signatures now use Pydantic request/response models (not raw primitives)
- **BREAKING**: Transport selection via CLI `--transport` flag (stdio/sse/http)
- Server now uses `create_mcp_server()` factory for testability
- Core business logic extracted to `FilesystemCore` (no FastMCP deps)

### Security
- Path traversal prevention via sandbox root enforcement
- Symlink attack mitigation (configurable)
- Atomic write operations prevent corruption
- Size limits prevent resource exhaustion
- Bearer token auth for remote transports

### Documentation
- Updated README with transport examples, auth, and Docker deployment
- Architecture overview in docs/
- Environment variable reference