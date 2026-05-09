# Contributing

Thank you for your interest in contributing!

## How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/project-name.git
cd project-name

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Run tests
pytest tests/ -v
```

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use [Ruff](https://docs.astral.sh/ruff/) for linting
- Run `ruff check .` before committing

## Pull Request Guidelines

- Keep PRs focused on a single change
- Include tests for new functionality
- Update documentation if needed
- Ensure all tests pass

## Reporting Issues

Use the [Issue Tracker](../../issues) to report bugs or request features.
Please use the provided issue templates.

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
