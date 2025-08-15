# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Strinks is a beer cost-performance monitoring system that scrapes beer prices from various online shops in Japan, matches them with Untappd data, and provides a web interface to find the best value beers.

## Key Commands

### Development

```bash
# Install the package in development mode
pip install -e .

# Format code (automatic git hook available)
isort -l 120 --lai 2 strinks tests setup.py
black --config pyproject.toml strinks tests setup.py

# Enable automatic formatting on commit
git config --local core.hooksPath .githooks/
```

### Testing & Linting

```bash
# Run all tests with tox (includes pytest, flake8, mypy)
tox

# Run tests only
pytest tests/

# Run linting
flake8 --config=tox.ini strinks/ tests/ setup.py

# Type checking
mypy --config-file=mypy.ini strinks/ tests/ setup.py
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
