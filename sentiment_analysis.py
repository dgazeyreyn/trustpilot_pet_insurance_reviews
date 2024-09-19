import pandas as pd
import os
from textblob import TextBlob
from nltk.sentiment.vader import SentimentIntensityAnalyzer


# Define the folder containing your CSV files
folder_path = 'input_files'

# Get a list of all CSV files in the folder
csv_files = [file for file in os.listdir(folder_path) if file.endswith('.csv')]

# Initialize an empty list to store dataframes
dfs = []

# Loop through each CSV file and append the dataframe to the list
for file in csv_files:
    file_path = os.path.join(folder_path, file)
    df = pd.read_csv(file_path) # Read each CSV file into a dataframe
    dfs.append(df) # Add the dataframe to the list

# Concatenate all the dataframes into one
combined_df = pd.concat(dfs, ignore_index=True)

# Split source column into url and page columns
combined_df[['url', 'page']] = combined_df['source'].str.split('?', expand=True)

# Map url to provider
provider_mapping = {'https://www.trustpilot.com/review/www.akcpetinsurance.com' :'AKC',
                 'https://www.trustpilot.com/review/aspcapetinsurance.com' : 'ASPCA',
                 'https://www.trustpilot.com/review/embracepetinsurance.com' : 'Embrace',
                 'https://www.trustpilot.com/review/fetchpet.com' : 'Fetch',
                 'https://www.trustpilot.com/review/figopetinsurance.com' : 'Figo',
                 'https://www.trustpilot.com/review/www.healthypawspetinsurance.com' : 'Healthy Paws',
                 'https://www.trustpilot.com/review/lemonade.com': 'Lemonade',
                 'https://www.trustpilot.com/review/petsbest.com' : 'Pets Best',
                 'https://www.trustpilot.com/review/www.pumpkin.care': 'Pumpkin',
                 'https://www.trustpilot.com/review/spotpetins.com': 'Spot'}
combined_df['provider'] = combined_df['url'].map(provider_mapping)

# Initialize VADER sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Ensure the 'provider' column exists
if 'provider' in combined_df.columns:
    
    # TextBlob Sentiment Analysis: Polarity and Subjectivity
    combined_df['textblob_polarity'] = combined_df['provider'].apply(lambda x: TextBlob(str(x)).sentiment.polarity)
    combined_df['textblob_subjectivity'] = combined_df['provider'].apply(lambda x: TextBlob(str(x)).sentiment.subjectivity)

    # VADER Sentiment Analysis: Compound score
    combined_df['vader_compound'] = combined_df['provider'].apply(lambda x: sia.polarity_scores(str(x))['compound'])

    # Assign sentiment categories for TextBlob
    combined_df['textblob_sentiment'] = combined_df['textblob_polarity'].apply(
        lambda score: 'positive' if score > 0 else ('neutral' if score == 0 else 'negative'))

    # Assign sentiment categories for VADER
    combined_df['vader_sentiment'] = combined_df['vader_compound'].apply(
        lambda score: 'positive' if score >= 0.05 else ('neutral' if -0.05 < score < 0.05 else 'negative'))

# Show the first few rows with sentiment categories
print(combined_df[['provider', 'textblob_polarity', 'textblob_sentiment', 'vader_compound', 'vader_sentiment']].head())

# Save the DataFrame with both sentiment analyses and categories to a CSV (if needed)
combined_df.to_csv('data_with_sentiment_categories.csv', index=False)