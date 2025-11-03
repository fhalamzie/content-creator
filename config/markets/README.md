# Market Configurations

This directory contains market-specific configuration files for the Universal Topic Research Agent.

## Structure

Each config file defines:
- **Market**: Domain, market, language, vertical
- **Collectors**: Which data sources to use (RSS, Reddit, Trends, Autocomplete)
- **Scheduling**: When to run collection and sync

## Available Configurations

### proptech_de.yaml
**German PropTech / SaaS**
- Domain: SaaS
- Market: Germany
- Language: German (de)
- Vertical: Proptech
- Keywords: 7 (PropTech, Smart Building, DSGVO, etc.)
- Custom Feeds: 7 (Heise, t3n, Golem, etc.)
- Competitors: 4 (ImmobilienScout24, Propstack, etc.)

### fashion_fr.yaml
**French Fashion / E-commerce**
- Domain: E-commerce
- Market: France
- Language: French (fr)
- Vertical: Fashion
- Keywords: 7 (Mode, Fashion Tech, etc.)
- Custom Feeds: 5 (Vogue, Elle, Madmoizelle, etc.)
- Competitors: 4 (Zalando, ASOS, etc.)

## Configuration Format

```yaml
# === Market Configuration ===
domain: SaaS                    # Business domain
market: Germany                 # Target market
language: de                    # ISO 639-1 language code
vertical: Proptech              # Industry vertical
target_audience: German SMBs in real estate

seed_keywords:
  - PropTech
  - Smart Building
  # ... more keywords

competitor_urls:
  - https://www.example.com
  # ... more competitors

# === Collector Configuration ===
collectors:
  rss_enabled: true
  reddit_enabled: true
  trends_enabled: true
  autocomplete_enabled: true

  custom_feeds:
    - https://www.heise.de/rss/heise-atom.xml
    # ... more feeds

  reddit_subreddits:
    - de
    - Finanzen
    # ... more subreddits

# === Scheduling Configuration ===
scheduling:
  collection_time: "02:00"      # 24-hour format
  notion_sync_day: monday       # Day of week
  lookback_days: 7              # Content lookback period
```

## Usage

### Python

```python
from src.utils.config_loader import ConfigLoader

# Load config
loader = ConfigLoader()
config = loader.load("proptech_de")

# Access values
print(config.market.domain)           # "SaaS"
print(config.market.language)         # "de"
print(config.market.seed_keywords)    # ["PropTech", "Smart Building", ...]

# Use in collectors
feeds = config.collectors.custom_feeds
subreddits = config.collectors.reddit_subreddits
```

### CLI Validation

```bash
# Validate all configs
python test_config_validation.py
```

## Creating New Configurations

1. **Copy an existing config**:
   ```bash
   cp config/markets/proptech_de.yaml config/markets/your_niche.yaml
   ```

2. **Edit required fields**:
   - `domain`: Your business domain (SaaS, E-commerce, etc.)
   - `market`: Your target market (Germany, France, US, etc.)
   - `language`: ISO 639-1 code (de, en, fr, etc.)
   - `vertical`: Your industry vertical
   - `seed_keywords`: 2-7 keywords for feed discovery

3. **Customize collectors**:
   - Add relevant RSS feeds for your niche
   - Specify relevant Reddit subreddits
   - Adjust scheduling to your needs

4. **Validate**:
   ```python
   from src.utils.config_loader import ConfigLoader
   loader = ConfigLoader()
   config = loader.load("your_niche")  # Should load without errors
   ```

## Per-Config Isolation

Each configuration is isolated:
- **Language detection** caches results per-config
- **Topic clustering** operates within config boundaries
- **Feed discovery** uses config-specific seed keywords
- **No cross-pollination** between German PropTech and French Fashion

This ensures clean, relevant topic discovery for each market.

## Validation

All configs are validated using Pydantic:
- **Required fields** must be present (domain, market, language, vertical, seed_keywords)
- **Seed keywords** must have at least 1 keyword
- **Scheduling** values must be valid (collection_time, notion_sync_day, lookback_days ≥ 1)
- **Collectors** default to enabled if not specified

## Examples

### Minimal Config

```yaml
domain: SaaS
market: Germany
language: de
vertical: Proptech
seed_keywords:
  - PropTech
```

All other values will use defaults:
- All collectors enabled
- Collection time: 02:00
- Notion sync: monday
- Lookback: 7 days

### Full Config

See `proptech_de.yaml` or `fashion_fr.yaml` for complete examples with all optional fields.
