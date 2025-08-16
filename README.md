# Strinks - Beer Cost-Performance Monitoring

Stonks + Drinks = ~terrible name idea~ Strinks

A system for finding the best value craft beers in Japan by scraping online shops and correlating with Untappd ratings.

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for fast package management (recommended)
- Untappd API credentials (for beer data)
- DeepL API key (for Japanese translations)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/strinks.git
cd strinks

# Install with uv (recommended - fast!)
uv sync
uv pip install -e .

# Or with regular pip
pip install -e .
```

### Configuration

Create a `.env` file with your API keys:

```bash
UNTAPPD_CLIENT_ID=your_client_id
UNTAPPD_CLIENT_SECRET=your_client_secret
DEEPL_API_KEY=your_deepl_key
OPENAI_API_KEY=your_openai_key  # Optional, for OCR features

# Optional: Proxy for Untappd OAuth (if your server IP is blocked by Cloudflare)
UNTAPPD_OAUTH_PROXY=https://user:pass@proxy-server:port
```

## Development

### Code Quality

The project uses pre-commit hooks to maintain code quality:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run all checks manually
uv run pre-commit run --all-files

# Run specific checks
uv run pre-commit run mypy --all-files
uv run pre-commit run ruff --all-files
```

### Testing

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest --cov=strinks tests/

# Run specific test file
uv run pytest tests/test_models.py -v
```

### Type Checking

The project maintains **zero mypy errors**:

```bash
uv run pre-commit run mypy --all-files
```

## Database Migrations

The project uses Alembic for database schema migrations:

```bash
# Generate a new migration after model changes
uv run alembic revision --autogenerate -m "Description of changes"

# Apply migrations to bring database to latest version
uv run alembic upgrade head

# View current migration status
uv run alembic current

# Downgrade to previous version
uv run alembic downgrade -1
```

## Usage

### CLI Commands

```bash
# Initialize the database
uv run strinks-init-db

# Scrape all shops for current beer prices
uv run strinks-scrape -v

# Scrape a specific shop
uv run strinks-scrape --shop-name volta

# Fetch user check-ins from Untappd
uv run strinks-fetch-had

# Fetch brewery information
uv run strinks-fetch-breweries

# Drop users table (for public DB export)
uv run strinks-drop-users -d path/to/db.sqlite
```

### Web Interface

```bash
# Run the Flask web server
uv run python -m strinks.web.app

# Access at http://localhost:5000
```

## Tech Stack

- **SQLModel**: Database ORM with Pydantic integration
- **Alembic**: Database schema migrations
- **Flask**: Web framework for the UI
- **BeautifulSoup4**: Web scraping
- **Pydantic**: Data validation
- **uv**: Fast Python package manager
- **pytest**: Testing framework
- **mypy**: Static type checking
- **ruff**: Fast Python linter
- **pre-commit**: Git hooks for code quality

## Database

The latest database (without the users table) is published [here](https://zeletochoy.github.io/strinks/db.sqlite) after every update in CI.

## Shops

### Currently Supported

- [Antenna America](https://www.antenna-america.com/)
- [Beerzilla](https://tokyo-beerzilla.myshopify.com/)
- [Chouseiya](https://www.chouseiya-beer.com/)
- [Craft Beer Market](https://www.craftbeermarket.jp/) (multiple locations)
- [CraftBeers](https://www.craftbeers.jp/)
- [Dig The Line](https://dig-the-line-store.com/)
- [Good Beer Faucets](https://gbfbottleshoppe.com/)
- [Goodbeer](https://goodbeer.jp/)
- [Hop Buds](https://hopbudsnagoya.com/)
- [IBrew](https://craftbeerbar-ibrew.com/)
- [Ichi Go Ichi Ale](https://151l.shop/)
- [Maruho](https://maruho-beer.com/)
- [Ohtsuki](http://www.ohtsuki-saketen.com/)
- [Slop Shop](https://slopshop.jp/)
- [Threefeet](https://threefeet.co.jp/)
- [Volta](http://beervolta.com/)

### TODO

- [Scissors](https://craftbeers.thebase.in/)
- [Uchu Brewing](https://uchubrew.shop-pro.jp/)
- [TDM 1874](https://search.rakuten.co.jp/search/mall/tdm1874/)
- [Distant Shores Brewing](https://en.dsbtokyo.shop/shop)
- [Jollys](https://www.ubereats.com/jp/tokyo/food-delivery/jollys/0Rr8RBPfTMyb7x89DH8mkQ?ps=1)
