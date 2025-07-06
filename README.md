# ArXiv Paper Fetcher

This project contains a Python script to fetch the latest computer science papers from the arXiv API. The collected data can be saved locally as JSONL files or sent to a remote API service for further processing, such as integration with the `arxiv-search` project.

## Features

-   Fetches recent papers from arXiv's computer science categories (`cs.*`).
-   Configurable time window for fetching (e.g., last 24 hours).
-   Two output modes:
    -   `local`: Saves papers to a local `*.jsonl` file.
    -   `api`: Sends papers to a specified API endpoint.
-   Supports authenticated API requests.
-   Easy to automate with cron jobs or GitHub Actions.

## Setup and Configuration

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd arxiv-search-ext
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**
    Create a `.env` file by copying the example file:
    ```bash
    cp .env.example .env
    ```
    Now, edit the `.env` file with your desired configuration.

### Environment Variables

| Variable                | Description                                                                                              | Default      | Example                                 |
| ----------------------- | -------------------------------------------------------------------------------------------------------- | ------------ | --------------------------------------- |
| `ARXIV_OUTPUT_MODE`     | The output mode. Can be `local` or `api`.                                                                | `local`      | `api`                                   |
| `OUTPUT_DIR`            | The directory to save local files if `ARXIV_OUTPUT_MODE` is `local`.                                     | `./output`   | `./data`                                |
| `FETCH_HOURS`           | The number of hours in the past to fetch papers from.                                                    | `24`         | `48`                                    |
| `ARXIV_API_SERVICE_URL` | The URL of the API service to send data to when `ARXIV_OUTPUT_MODE` is `api`.                              | (none)       | `http://localhost:8000/api/papers`      |
| `ARXIV_ENABLE_AUTH`     | Set to `true` to enable API key authentication for the API service.                                      | `false`      | `true`                                  |
| `ARXIV_API_KEY`         | The API key to use for authentication if `ARXIV_ENABLE_AUTH` is `true`.                                  | (none)       | `your-secret-api-key`                   |

## Usage

After setting up the configuration, you can run the script directly:

```bash
python3 arxiv_fetch.py
```

-   If `ARXIV_OUTPUT_MODE` is `local`, new `*.jsonl` files will be created in the specified `OUTPUT_DIR`.
-   If `ARXIV_OUTPUT_MODE` is `api`, the script will attempt to POST the data to `ARXIV_API_SERVICE_URL`.

## Automation

You can automate the execution of this script to regularly fetch new papers.

### Cron Job

You can set up a cron job to run the script on a schedule. For example, to run it every day at midnight:

```cron
0 0 * * * /path/to/your/project/venv/bin/python /path/to/your/project/arxiv_fetch.py >> /path/to/your/project/cron.log 2>&1
```

Make sure to use the absolute paths to your Python executable and the script.

### GitHub Actions

You can use GitHub Actions to run the script on a schedule. This is the recommended method for projects hosted on GitHub.

Create a file named `.github/workflows/fetch_arxiv_papers.yml` with the following content:

```yaml
name: Fetch Latest ArXiv Papers

on:
  schedule:
    # Runs every day at midnight UTC
    - cron: '0 0 * * *'
  workflow_dispatch: # Allows manual triggering

jobs:
  fetch-papers:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run ArXiv Fetch Script
        env:
          ARXIV_OUTPUT_MODE: ${{ secrets.ARXIV_OUTPUT_MODE }}
          ARXIV_API_SERVICE_URL: ${{ secrets.ARXIV_API_SERVICE_URL }}
          ARXIV_ENABLE_AUTH: ${{ secrets.ARXIV_ENABLE_AUTH }}
          ARXIV_API_KEY: ${{ secrets.ARXIV_API_KEY }}
          FETCH_HOURS: '24'
        run: python3 arxiv_fetch.py
```

#### GitHub Secrets

For the GitHub Action to work, you need to configure secrets in your repository settings (`Settings` > `Secrets and variables` > `Actions`). This keeps your sensitive information, like API keys, secure.

You should create the following secrets:

-   `ARXIV_OUTPUT_MODE`: e.g., `api`
-   `ARXIV_API_SERVICE_URL`: e.g., `https://your-arxiv-search-project.com/api/papers`
-   `ARXIV_ENABLE_AUTH`: e.g., `true`
-   `ARXIV_API_KEY`: Your secret API key.

This setup assumes you are using the `api` mode. If you want to use `local` mode and commit the results back to the repository, the workflow will need to be modified to handle committing and pushing files.
