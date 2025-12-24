# Contributing to AI Project Analyzer

🎉 First off, thank you for considering contributing to AI Project Analyzer!

This document provides guidelines and instructions for contributing to this project.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

---

## 📜 Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow:

- **Be Respectful**: Treat everyone with respect and kindness
- **Be Collaborative**: Work together and help each other
- **Be Professional**: Keep discussions focused and constructive
- **Be Inclusive**: Welcome newcomers and diverse perspectives

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- [UV](https://github.com/astral-sh/uv) package manager (recommended)
- Git
- Docker (optional, for containerized development)

### Fork and Clone

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/ai-project-analyzer.git
cd ai-project-analyzer
```

3. **Add upstream** remote:

```bash
git remote add upstream https://github.com/ruslanmv/ai-project-analyzer.git
```

---

## 🛠️ Development Setup

### Install Dependencies

```bash
# Install UV if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (including dev)
make dev

# Or manually with UV
uv sync
```

### Configure Environment

```bash
# Copy sample environment file
cp .env.sample .env

# Edit .env and configure:
# - OPENAI_API_KEY (for OpenAI models)
# - OLLAMA_URL (for local Ollama)
# - Or other LLM provider credentials
```

### Verify Setup

```bash
# Run tests
make test

# Run linter
make lint

# Run type checker
make type-check
```

---

## 💡 How to Contribute

### Reporting Bugs

Found a bug? Please open an issue with:

- **Clear title** describing the issue
- **Steps to reproduce** the bug
- **Expected behavior** vs actual behavior
- **Environment details** (OS, Python version, etc.)
- **Logs or screenshots** if applicable

**Template:**
```markdown
## Bug Description
[Clear description]

## Steps to Reproduce
1. ...
2. ...
3. ...

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11.5]
- Version: [e.g., 2.0.0]
```

### Suggesting Features

Have an idea? Open an issue with:

- **Problem statement**: What problem does this solve?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches you thought about
- **Additional context**: Any relevant information

### Working on Issues

1. **Comment** on the issue you want to work on
2. **Wait** for assignment or approval from maintainers
3. **Create a branch** with a descriptive name:

```bash
git checkout -b feature/add-amazing-feature
# or
git checkout -b fix/resolve-bug-123
```

---

## 📝 Coding Standards

### Style Guide

We use strict code quality tools:

- **Ruff** for linting and formatting
- **mypy** for type checking
- **100% type hints** required
- **Pydantic V2** for data validation

### Code Quality Checklist

Before submitting code, ensure:

- ✅ All tests pass: `make test`
- ✅ No linting errors: `make lint`
- ✅ No type errors: `make type-check`
- ✅ Code is formatted: `make format`
- ✅ New code has tests
- ✅ Docstrings follow Google style

### Python Style

```python
"""
Module docstring explaining purpose.

Detailed description if needed.
"""

from __future__ import annotations

from typing import Any


class MyClass:
    """
    Short description of class.

    Attributes:
        name: Description of name attribute
        value: Description of value attribute
    """

    def __init__(self, name: str, value: int) -> None:
        """
        Initialize MyClass.

        Args:
            name: The name parameter
            value: The value parameter
        """
        self.name = name
        self.value = value

    def process(self, data: dict[str, Any]) -> str:
        """
        Process the data.

        Args:
            data: Input data dictionary

        Returns:
            Processed result string

        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Data cannot be empty")
        return f"{self.name}: {len(data)}"
```

### Commit Messages

Follow **Conventional Commits**:

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Build/tooling changes

**Examples:**
```
feat(cli): add verbose logging option

fix(workflow): resolve memory leak in large file processing

docs(readme): update installation instructions

test(models): add validation tests for FileAnalysisResult
```

---

## 🧪 Testing Guidelines

### Writing Tests

- **Unit tests** for individual components
- **Integration tests** for workflows
- **Use fixtures** from `tests/conftest.py`
- **Mock external services** (LLMs, APIs)
- **Aim for >80% coverage**

### Test Structure

```python
"""
Tests for MyModule.

Comprehensive test coverage for all functionality.
"""

from __future__ import annotations

import pytest


class TestMyClass:
    """Tests for MyClass."""

    def test_valid_input(self) -> None:
        """Test that valid input produces expected output."""
        # Arrange
        obj = MyClass("test", 42)

        # Act
        result = obj.process({"key": "value"})

        # Assert
        assert result == "test: 1"

    def test_invalid_input_raises(self) -> None:
        """Test that invalid input raises appropriate error."""
        obj = MyClass("test", 42)

        with pytest.raises(ValueError, match="Data cannot be empty"):
            obj.process({})
```

### Running Tests

```bash
# All tests
make test

# Fast (no coverage)
make test-fast

# Specific test
uv run pytest tests/unit/test_models.py -v

# With coverage report
uv run pytest --cov --cov-report=html
open htmlcov/index.html
```

---

## 🔄 Pull Request Process

### Before Submitting

1. **Update from upstream**:
```bash
git fetch upstream
git rebase upstream/main
```

2. **Run full audit**:
```bash
make audit
```

3. **Update documentation** if needed

4. **Add tests** for new features

### Submitting PR

1. **Push** your branch:
```bash
git push origin feature/your-feature
```

2. **Create PR** on GitHub with:
   - Clear title and description
   - Link to related issues
   - Screenshots/examples if applicable
   - Checklist of changes

3. **PR Template**:
```markdown
## Description
[Clear description of changes]

## Motivation
[Why is this change needed?]

## Changes Made
- [ ] Item 1
- [ ] Item 2
- [ ] Item 3

## Testing
[How was this tested?]

## Checklist
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Backward compatible (or documented breaking changes)

## Related Issues
Fixes #123
```

### Review Process

- Maintainers will review within 3-5 business days
- Address feedback and push updates
- Once approved, maintainers will merge

---

## 🎯 Good First Issues

Look for issues labeled:
- `good first issue` - Perfect for newcomers
- `help wanted` - Community contributions welcome
- `documentation` - Documentation improvements

---

## 💬 Community

### Getting Help

- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Report bugs or request features
- **Email**: contact@ruslanmv.com

### Recognition

Contributors are recognized in:
- README.md
- Release notes
- GitHub contributors page

---

## 📚 Additional Resources

- [Project Architecture](ARCHITECTURE.md)
- [API Documentation](API.md)
- [README](../README.md)

---

## 🙏 Thank You!

Your contributions make this project better for everyone. Thank you for being part of the community!

---

*Made with ❤️ by [Ruslan Magana](https://ruslanmv.com)*
