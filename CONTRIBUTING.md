# Contributing to Legal Atlas

Thanks for your interest in improving Legal Atlas. This guide covers the development workflow and code standards.

## Development Setup

1. **Clone and install:**
   ```bash
   git clone <repository-url>
   cd legal-rag
   pip install -e ".[dev]"
   ```

2. **Install pre-commit hooks (recommended):**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Code Standards

### Python Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check code
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

**Style guidelines:**
- Line length: 110 characters
- Type hints encouraged for public APIs
- Docstrings for modules and public functions
- F-strings preferred over `.format()` or `%`

### JavaScript/CSS

**Frontend code standards:**
- ES6+ syntax (arrow functions, const/let, async/await)
- No external frameworks - vanilla JS only
- Mobile-first responsive design
- Accessibility: ARIA labels, semantic HTML
- No inline styles - use CSS classes

### Commit Messages

Use clear, descriptive commits:

```bash
# Good
git commit -m "Fix citation duplicate display in search results"
git commit -m "Add error handling for health API failures"

# Avoid
git commit -m "fix bug"
git commit -m "update stuff"
```

## Project Structure

```
legal_rag/
├── __main__.py       # CLI entry point
├── config.py         # Configuration constants
├── ingestion.py      # PDF extraction and parsing
├── chunking.py       # Document segmentation
├── indexing.py       # Embedding generation
├── retrieval.py      # Search implementation
├── generation.py     # LLM integration
├── evaluation.py     # Quality metrics
├── server.py         # HTTP server
├── storage.py        # Data persistence
└── web/              # Frontend assets
```

## Testing

### Running Tests

```bash
# All tests
python -m pytest

# Specific test file
python -m pytest tests/test_pipeline.py

# With coverage
python -m pytest --cov=legal_rag
```

### Writing Tests

- Place tests in `tests/` directory
- Use descriptive test names: `test_retrieval_handles_empty_query`
- Mock external dependencies (LLM APIs, file I/O when appropriate)
- Test edge cases: empty input, missing data, malformed responses

Example:

```python
def test_chunking_respects_max_length():
    """Chunks should not exceed configured character limit."""
    result = chunk_text(long_text, max_chars=1600)
    assert all(len(chunk["text"]) <= 1600 for chunk in result)
```

## Adding Features

### 1. New Search Methods

To add a retrieval method:

1. Implement in `retrieval.py`:
   ```python
   def new_method_search(self, query: str, top_k: int) -> list[dict]:
       # Implementation
       pass
   ```

2. Register in `search()` method
3. Add CLI option in `__main__.py`
4. Add tests in `tests/test_retrieval.py`
5. Update evaluation in `evaluation.py`

### 2. New Document Types

To support new legal document formats:

1. Update parser in `ingestion.py`
2. Adjust chunking logic in `chunking.py` if needed
3. Update `config/corpus.json` schema if needed
4. Add sample document to test corpus
5. Run extraction and verify output

### 3. Frontend Changes

For UI modifications:

1. Edit `legal_rag/web/` files (HTML/CSS/JS)
2. Test in multiple browsers (Chrome, Firefox, Safari)
3. Verify mobile responsiveness (< 768px width)
4. Check accessibility (keyboard navigation, screen readers)
5. Test with server running: `python -m legal_rag serve`

## Pull Request Process

1. **Branch from main:**
   ```bash
   git checkout -b feature/descriptive-name
   ```

2. **Make changes:**
   - Write code
   - Add/update tests
   - Update documentation if needed

3. **Run quality checks:**
   ```bash
   ruff check .
   ruff format .
   python -m pytest
   ```

4. **Commit and push:**
   ```bash
   git add .
   git commit -m "Clear description of changes"
   git push origin feature/descriptive-name
   ```

5. **Open PR:**
   - Describe what changed and why
   - Link any related issues
   - Add screenshots for UI changes

## Code Review

Reviewers will check:
- Code quality and style compliance
- Test coverage for new code
- Documentation updates
- No breaking changes to public APIs
- Performance impact (if applicable)

## Performance Considerations

When optimizing:
- Profile before optimizing (don't guess)
- Document trade-offs (speed vs memory vs accuracy)
- Benchmark changes with real data
- Consider impact on 2GB RAM constraint

## Documentation

Update docs when:
- Adding new CLI commands
- Changing API signatures
- Adding configuration options
- Modifying data formats
- Changing deployment requirements

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for design questions
- Check existing issues before creating new ones

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).
