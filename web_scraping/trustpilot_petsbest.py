import json
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs

# Identifying last page of url
url = "https://www.trustpilot.com/review/petsbest.com"
response = requests.get(url)
html = response.content
soup = bs(html, "html.parser")
results = soup.find(id="__NEXT_DATA__")
json_object = json.loads(results.contents[0])
last_page = json_object["props"]["pageProps"]["filters"]["pagination"]["totalPages"]

print(last_page)

# Creating list of urls with a limit based on last_page above
page = 1
urls = []
while True:
    if page <= last_page:
        url = f"https://www.trustpilot.com/review/petsbest.com?page={page}"
        urls.append(url)
        page = page + 1
    else:
        break

print(urls)

# Looping through list of urls above
# Extracting relevant reviews information from each url
# Appending relevant information from each url to a dataframe 
all_dfs = []
for url in urls:
    response = requests.get(url)
    html = response.content
    soup = bs(html, "html.parser")
    results = soup.find(id="__NEXT_DATA__")
    json_object = json.loads(results.contents[0])
    reviews = json_object["props"]["pageProps"]["reviews"]
    ids = pd.Series([sub["id"] for sub in reviews])
    filtered = pd.Series([sub["filtered"] for sub in reviews])
    pending = pd.Series([sub["pending"] for sub in reviews])
    text = pd.Series([sub["text"] for sub in reviews])
    rating = pd.Series([sub["rating"] for sub in reviews])
    title = pd.Series([sub["title"] for sub in reviews])
    likes = pd.Series([sub["likes"] for sub in reviews])
    experienced = pd.Series([sub["dates"]["experiencedDate"] for sub in reviews])
    published = pd.Series([sub["dates"]["publishedDate"] for sub in reviews])
    source = url
    df = pd.DataFrame(
        {
            "id": ids,
            "filtered": filtered,
            "pending": pending,
            "text": text,
            "rating": rating,
            "title": title,
            "likes": likes,
            "experienced": experienced,
            "published": published,
            "source": source,
        }
    )
    all_dfs.append(df)

final_df = pd.concat(all_dfs)

# Saving results to csv
final_df.to_csv('petsbest_reviews.csv', index=False)
