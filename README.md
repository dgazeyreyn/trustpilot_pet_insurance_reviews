# Trustpilot Pet Insurance Reviews

## Project Overview

This project builds an end-to-end analytics pipeline for collecting, processing, and analyzing Trustpilot reviews for U.S. pet insurance providers. The goal is to surface meaningful, data-driven insights that help consumers understand how providers differ across key dimensions such as claims processing, customer service, reimbursement experience, and overall satisfaction.

The project is intentionally designed to resemble a real-world analytics engineering workflow rather than a one-off analysis. It emphasizes incremental data ingestion, reproducibility, and a clear separation between raw data, curated outputs, and downstream modeling.

---

## High-Level Architecture

The project is organized into three logical layers:

1. **Ingestion (Web Scraping)** – Collects Trustpilot reviews incrementally by provider
2. **Curation & Modeling** – Normalizes, merges, and prepares data for analysis
3. **Analysis & Theming** – Applies unsupervised topic modeling to extract review themes

```
trustpilot_pet_insurance_reviews/
│
├── web_scraping/
│   ├── raw/                # Historical provider-level review CSVs (local, not versioned)
│   ├── incremental/        # Incremental review pulls (local, not versioned)
│   ├── curated/            # Merged, provider-level outputs
│   ├── scraper.py          # Incremental Trustpilot scraper
│   ├── merge_reviews.py    # Merges raw + incremental data
│   └── providers.yaml      # Provider URLs and last_collected timestamps
│
├── modeling/
│   ├── 03_merge_for_modeling.py
│   ├── 04_bertopic_baseline.py
│   └── 05_theme_labeling.py
│
├── data/
│   └── modeling/           # Modeling outputs (local, not versioned)
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Environment Setup

This project relies on modern NLP tooling (e.g., BERTopic, sentence-transformers, PyTorch) that can be challenging to install via pip alone, particularly on macOS. For this reason, Conda is the recommended environment manager.

### Prerequisites

- Git
- Conda (Miniforge or Anaconda recommended)
    - Miniforge: https://github.com/conda-forge/miniforge

### Create and Activate the Environment

From the project root:

conda env create -f environment.yml
conda activate trustpilot

This will install all required dependencies, including:

- Python
- pandas / numpy
- BERTopic and NLP dependencies
- PyTorch
- numba / llvmlite (via conda-forge)

Note: The environment has been validated using a clean clone to ensure reproducibility.

### Verify Installation (Optional)

You can quickly verify the core dependencies:

python - <<EOF
from bertopic import BERTopic
import torch
import numpy
print("BERTopic, PyTorch, and NumPy are available.")
EOF

### Running the Pipeline

With the environment active, scripts can be run directly from the project root, for example:

python web_scraping/scraper.py
python web_scraping/merge_reviews.py
python modeling/04_bertopic_baseline.py
python modeling/05_theme_labeling.py

### Notes on requirements.txt

A requirements.txt file is included for reference, but it is not sufficient on its own for installing BERTopic and related dependencies on all systems. The environment.yml file should be treated as the source of truth.

## Web Scraping & Incremental Ingestion

### Provider Configuration

All providers are defined in `providers.yaml`, which includes:

* Provider name
* Trustpilot review URL
* `last_collected` timestamp

This file acts as lightweight ingestion metadata and allows the scraper to operate incrementally.

---

### First Run vs Incremental Runs

This project intentionally distinguishes between **first-time execution** and **subsequent incremental runs**.

**First Run**

* No historical data exists locally
* The scraper collects the full available Trustpilot review history for each provider
* Results are written to `web_scraping/incremental/`
* Merged outputs are written to `web_scraping/curated/`
* `last_collected` timestamps are updated per provider

**Incremental Runs**

* Existing review data is reused
* Only reviews published after each provider’s `last_collected` timestamp are scraped
* New reviews are appended and deduplicated
* Provider-level timestamps are updated independently

Raw and incremental CSVs are intentionally **not committed to GitHub**. They represent local ingestion state, similar to a database or object storage layer in a production system.

---

### Merging Logic

The `merge_reviews.py` script:

* Combines historical (`raw/`) and incremental (`incremental/`) review data
* Handles providers with or without prior history
* Deduplicates reviews by ID
* Normalizes timestamps
* Writes curated provider-level outputs
* Updates `providers.yaml` with the latest `last_collected` value per provider

---

## Modeling & Theme Extraction

### Merge for Modeling

`03_merge_for_modeling.py` consolidates all provider-level curated CSVs into a single modeling-ready dataset. This step standardizes columns, parses timestamps, and adds provider identifiers.

---

### Unsupervised Theme Modeling

`04_bertopic_baseline.py` applies BERTopic to extract themes from review text across all ratings (not limited to 5-star reviews). Key characteristics:

* Sentence-transformer embeddings
* Density-based clustering
* Automatic topic reduction
* Noise handling via outlier topics

This approach allows themes to emerge directly from the data rather than relying on manually curated vocabularies.

---

### Theme Labeling & Aggregation

`05_theme_labeling.py` maps discovered topics into higher-level, human-readable themes and produces aggregated outputs suitable for downstream visualization, including:

* Theme frequency by provider
* Average rating by theme and provider
* Monthly theme trends by provider

These outputs are designed to support dashboard-style analysis (e.g., Tableau) that combines narrative insights with quantitative comparisons.

---

## Design Philosophy

This project prioritizes:

* Incremental, state-aware ingestion
* Separation of code and data
* Reproducibility without committing large datasets
* Scalable patterns inspired by analytics engineering best practices

While CSVs are used for storage, the architecture mirrors production ELT pipelines that rely on persisted state, watermarks, and idempotent processing.

---

## Notes on Data Usage

Trustpilot reviews are publicly available user-generated content. This project is intended for educational and analytical purposes only and is not affiliated with or endorsed by Trustpilot or any pet insurance provider.

---

## Future Enhancements

Potential next steps include:

* Time-based theme evolution analysis
* Sentiment-aware theme modeling
* Migration from CSV storage to a database or cloud object store
* Orchestration via scheduled jobs or workflows

---

## Contact

For questions or discussion about this project, feel free to reach out via GitHub.
