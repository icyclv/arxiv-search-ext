# arXiv-search-ext

A tool for the arXiv-search system (to be open-sourced) that automatically collects the latest papers from arXiv. It periodically fetches newly published Computer Science papers from arXiv and either sends them to a specified API service or saves them to a local file.

## Features

- Automatically fetches CS papers published within a specified time range (default 24 hours)
- Supports batch retrieval while respecting arXiv API rate limits
- Flexible output options (local JSONL files or HTTP API)
- Supports request signature verification
- Can be run via GitHub Actions or local cron jobs
- Automatic deduplication of papers

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/arxiv-search-ext.git
cd arxiv-search-ext
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Basic Configuration:
- `OUTPUT_MODE`: (Optional) Output mode, available options:
  - `local`: Save to local files (default)
  - `api`: Send to remote API service
- `FETCH_HOURS`: (Optional) How many hours of papers to fetch, default 24 hours

Local Mode Configuration (Default):
- `OUTPUT_DIR`: (Optional) Local output directory, defaults to `output`

API Mode Configuration:
- `API_SERVICE_URL`: (Required when OUTPUT_MODE=api) URL of the API service
- `ENABLE_SIGNATURE`: (Optional) Enable request signature verification, set to "false" to disable
- `ARXIV_IMPORT_PRIVATE_KEY`: (Required when signature verification is enabled) Private key for signing requests

### Signature Verification Setup

If you need to enable signature verification, follow these steps:

1. Generate key pair:
```bash
python generate_key_pair.py > keys.txt
```

2. From the generated keys.txt, get the private and public keys:
   - Configure the private key in the collector's `ARXIV_IMPORT_PRIVATE_KEY` environment variable
   - Configure the public key in the API service for signature verification

## Usage

### Local Execution

1. Configure environment variables (optional):

```bash
# Use default configuration (local file mode)
python arxiv_fetch.py

# Or customize configuration
export OUTPUT_DIR="./papers"  # Optional, custom output directory
export FETCH_HOURS=24  # Optional, fetch papers from last 24 hours

# For API mode
export OUTPUT_MODE=api
export API_SERVICE_URL="http://your-api-server/import"
export ENABLE_SIGNATURE=false
```

2. Run the script:
```bash
python arxiv_fetch.py
```

### Cron Job Configuration

On Linux/Unix systems, you can configure a cron job:

```bash
# Edit crontab
crontab -e

# Add cron job (e.g., run at 2 AM daily using default local file mode)
0 2 * * * cd /path/to/arxiv-search-ext && python arxiv_fetch.py

# Or use API mode
# 0 2 * * * cd /path/to/arxiv-search-ext && OUTPUT_MODE=api API_SERVICE_URL="http://your-api-server/import" python arxiv_fetch.py
```

### GitHub Actions

1. Create `.github/workflows/fetch.yml` file in your repository:

```yaml
name: Fetch arXiv Papers

on:
  schedule:
    - cron: '0 2 * * *'  # Run at 2 AM UTC daily
  workflow_dispatch:      # Support manual trigger

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.x'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run fetch script
        env:
          OUTPUT_MODE: ${{ secrets.OUTPUT_MODE }}
          API_SERVICE_URL: ${{ secrets.API_SERVICE_URL }}
          ENABLE_SIGNATURE: ${{ secrets.ENABLE_SIGNATURE }}
          ARXIV_IMPORT_PRIVATE_KEY: ${{ secrets.ARXIV_IMPORT_PRIVATE_KEY }}
          FETCH_HOURS: ${{ secrets.FETCH_HOURS }}
          OUTPUT_DIR: ${{ secrets.OUTPUT_DIR }}
        run: python arxiv_fetch.py
```