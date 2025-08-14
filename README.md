Pet Insurance Review Sentiment Analysis 🐾
Analyzed ~27,000 Trustpilot reviews (2015–2024) for 10 major pet insurance providers to uncover what customers love (and dislike) most — and how each company stands out.

Key highlights:

🔍 Web scraping with Python to collect review text, ratings, and metadata.

🧠 Sentiment analysis with TextBlob & VADER, benchmarked against star ratings.

📊 Statistical term analysis to identify significant differentiators.

📈 Interactive Tableau dashboard for exploring results.

Providers covered: AKC, ASPCA, Embrace, Fetch, Figo, Healthy Paws, Lemonade, Pets Best, Pumpkin, Spot.

View the Dashboard <!-- Replace # with actual Tableau dashboard link -->

Table of Contents
Overview

Providers Covered

Repository Structure

Data Fields

Methodology

Installation

Usage

Results

License

Overview
This analysis aimed to:

Extract and compile reviews from Trustpilot for major pet insurance providers.

Apply sentiment analysis models to classify review tone.

Identify statistically significant differentiators in customer feedback.

Deliver insights in an interactive Tableau dashboard for competitive tracking.

Providers Covered
AKC

ASPCA

Embrace

Fetch

Figo

Healthy Paws

Lemonade

Pets Best

Pumpkin

Spot

Note: Reviews in .csv files are current as of 2024-04-05.

Repository Structure
csharp
Copy
Edit
.
├── web_scraping/
│   ├── Python scripts for data extraction
│   ├── CSV files containing raw reviews
│
├── positive_reviews_analysis/
│   ├── Jupyter Notebook with sentiment and statistical analysis
│
└── README.md
Data Fields
Field	Example	Description
id	660d9183a8ec9c50ace577a2	Review unique ID
filtered	FALSE	Whether review is filtered
pending	FALSE	Whether review is pending approval
text	Amanda was terrific...	Review body
rating	5	Star rating
title	Amanda was terrific	Review title
likes	0	Number of likes
experienced	2024-04-02T00:00:00.000Z	Date of experience
published	2024-04-02T20:58:35.000Z	Publication date
source	https://www.trustpilot.com/review/fetchpet.com?page=8	Review URL

Methodology
1. Data Acquisition
Scraped ~27k reviews using Python (json, requests, BeautifulSoup).

Captured review text, star ratings, and metadata from Trustpilot.

2. Sentiment Analysis
Applied TextBlob and VADER classifiers.

Defined “expected sentiment” from star ratings:

≥ 4 → Positive

= 3 → Neutral

≤ 2 → Negative

Compared classifier accuracy via regression and classification reports.

3. Positive Review Analysis
Preprocessed text: tokenization, stopword removal, stemming, lemmatization.

Created Bag of Words (~294k terms) → reduced to ~280 high-priority terms with client input.

Focused on Ease, Efficiency, Service & Support.

4. Statistical Testing
Calculated observed vs. expected counts per provider-term pair.

Restricted to counts >5 across providers.

Ran Chi-square independence tests and computed odds ratios with 95% CIs.

5. Visualization
Built interactive Tableau dashboard to display results.

Installation
bash
Copy
Edit
# Clone the repository
git clone https://github.com/your-username/pet-insurance-reviews.git

# Navigate into the repo
cd pet-insurance-reviews

# Install dependencies
pip install -r requirements.txt
Usage
Run Web Scraping Scripts

bash
Copy
Edit
python web_scraping/scraper.py
(Adjust filenames and parameters as needed)

Run Analysis
Open and execute the Jupyter Notebook in positive_reviews_analysis/.

Results
Statistically significant differentiators in customer feedback identified for each provider.

Insights available in an interactive Tableau dashboard (view here). <!-- Replace # with actual Tableau dashboard link -->

License
This project is licensed under the MIT License.
