# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Strinks is a beer cost-performance monitoring system that scrapes beer prices from various online shops in Japan, matches them with Untappd data, and provides a web interface to find the best value beers.

## Recent Major Changes (2025-08-16)

### Migration to Modern Stack

- **SQLAlchemy → SQLModel**: Full migration for better Pydantic integration
- **setup.py → pyproject.toml**: Using `uv` package manager for faster dependency management
- **Type Safety**: Achieved zero mypy errors (from 246 errors!)
- **Pre-commit Hooks**: Automated code quality with ruff, black, mypy, pyupgrade
- **Timezone-aware Datetimes**: All datetime fields now properly handle JST timezone
- **Test Suite**: Added comprehensive tests for models, shops, and utilities

## Key Commands

### Development

```bash
# Install dependencies with uv (fast!)
uv sync

# Run any command with uv
uv run <command>

# Install the package in development mode
uv pip install -e .

# Pre-commit hooks (runs automatically on commit)
uv run pre-commit run --all-files

# Run specific pre-commit hook
uv run pre-commit run mypy --all-files
uv run pre-commit run ruff --all-files

# Auto-fix issues with pre-commit
uv run pre-commit run --all-files --hook-stage manual
```

### Testing & Linting

```bash
# Run all tests
uv run pytest tests/

# Run tests excluding integration tests
uv run pytest tests/ -k "not integration"

# Run specific test file
uv run pytest tests/test_models.py -v

# Run with coverage
uv run pytest --cov=strinks tests/

# Type checking (should show 0 errors!)
uv run pre-commit run mypy --all-files
```

### CLI Tools

```bash
# Initialize database
strinks-init-db

# Scrape all shops
strinks-scrape -v

# Fetch user check-ins from Untappd
strinks-fetch-had

# Drop users table (for public DB export)
strinks-drop-users -d path/to/db.sqlite

# Fetch brewery information
strinks-fetch-breweries
```

## Architecture

### Core Components

1. **Shop Scrapers** (`strinks/api/shops/`)
   - Each shop has its own scraper module inheriting from `Shop` base class
   - Scrapers extract `ShopBeer` objects with price, volume, and availability info
   - Translation and romaji conversion for Japanese beer names

2. **Untappd Integration** (`strinks/api/untappd/`)
   - Multiple backends: API (with app/user tokens) and web scraping fallback
   - Caching mechanism to avoid redundant API calls
   - Beer matching with fuzzy search and translation support

3. **Database Layer** (`strinks/db/`)
   - SQLAlchemy models for Beer, Shop, Offering, User, etc.
   - `BeerDB` class provides high-level interface for all DB operations
   - SQLite database with read-only mode support

4. **Web Interface** (`strinks/web/`)
   - Flask application for browsing beer offerings
   - Cost-performance ranking with customizable value factor
   - User authentication via Untappd OAuth

### Data Flow

1. Shop scrapers fetch current beer offerings
2. Untappd client searches for each beer to get ratings and metadata
3. Data is stored in SQLite database with relationships between beers, shops, and offerings
4. Web interface queries DB to show best value beers based on price/ml and rating

### Key Environment Variables

Required for full functionality:

- `UNTAPPD_CLIENT_ID` - Untappd API client ID
- `UNTAPPD_CLIENT_SECRET` - Untappd API client secret
- `DEEPL_API_KEY` - DeepL API key for translations
- `OPENAI_API_KEY` - OpenAI API key for OCR/parsing assistance

### Important Files

- `strinks/api/untappd/untappd_cache.json` - Cache for Untappd beer lookups
- `strinks/db.sqlite` - Main SQLite database
- `strinks/api/translation.py` - Japanese brewery name translations
- `strinks/api/shops/__init__.py` - Base shop scraper interface

## Implementation Notes

### SQLModel vs SQLAlchemy

- Now using SQLModel throughout for better Pydantic integration
- All queries use modern SQLModel API: `select()`, `where()`, `col()`
- No more legacy `query()` calls
- Models in `strinks/db/tables.py` use SQLModel with proper type hints

### Type Safety

- Achieved zero mypy errors - maintain this!
- Avoid type ignores - think through proper solutions
- BeautifulSoup operations need `isinstance(item, Tag)` checks
- Use `Callable[[], Shop]` for shop factory functions

### Datetime Handling

- All datetime fields are timezone-aware (JST)
- Database might return naive datetimes - code handles both
- Always use `now_jst()` from `strinks.api.utils` for current time
- `updated_at` fields use `Column(DateTime(timezone=True))`

### Testing

- Tests use isolated temporary databases (not in-memory due to SQLModel)
- Fixtures properly scoped to avoid conflicts
- Integration tests marked with `@pytest.mark.integration`

### Rate Limiting

- `RateLimitedSession` class provides per-domain rate limiting
- Default 0.5s between requests, configurable per domain
- Thread-safe with locks for concurrent requests
- Untappd API has 1s rate limit configured
- Usage: `get_retrying_session(rate_limit=0.5, domain_limits={"api.example.com": 1.0})`

### Shop Scrapers

- `ShopBeer` now uses Pydantic BaseModel (not attrs)
- Validation via `model_validator` to raise `NotABeerError`
- Shop map returns `Callable[[], Shop]` to handle both classes and partials
- CBM locations created dynamically with `partial(CBM, location=loc)`
