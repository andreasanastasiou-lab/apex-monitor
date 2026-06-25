# Security Policy — Apex Monitor

## Deployment

- FastAPI binds to `127.0.0.1` only. It must never be exposed on `0.0.0.0` or a public interface without a reverse proxy with TLS in front.
- InfluxDB listens on `localhost` only. It must not be reachable from the network directly.
- No service in this stack should be exposed to the public internet without TLS termination and authentication.

## Secrets Management

- All secrets (InfluxDB token, Anthropic API key, SNMP credentials, SSH keys) are stored in a `.env` file at runtime.
- `.env` is listed in `.gitignore` and must never be committed to version control.
- `.env.template` contains placeholder values only and is safe to commit.
- `config.yaml` contains device topology and is also excluded from Git as it may contain internal IP addresses.

## SNMP

- SNMPv3 with authentication (SHA) and privacy (AES) is the preferred configuration.
- SNMPv1/v2c community strings offer no encryption or authentication and should be avoided.
- All SNMP credentials are stored in `.env` or injected at runtime, not hardcoded in `config.yaml`.

## SSH

- SSH access uses key-based authentication only. Password-based SSH is not supported.
- The monitoring user should have the minimum required privileges (read-only where possible).

## Authentication (Roadmap)

- Phase 4 will introduce JWT-based authentication for all API endpoints.
- Until then, the API must only be accessible from localhost or a trusted internal network.

## Reporting a Vulnerability

Report security issues to the IT department or the project maintainer directly. Do not open public GitHub issues for security vulnerabilities.
