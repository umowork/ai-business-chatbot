# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public issue for security vulnerabilities.**

Instead, please send an email to: **umawork@users.noreply.github.com**

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 1 week
- **Fix release**: depends on severity

## Security Best Practices

When deploying this project:

- Never commit `.env` files or API keys
- Use environment variables for all secrets
- Keep dependencies updated (`pip install --upgrade`)
- Run behind a reverse proxy (nginx) in production
- Enable HTTPS in production
