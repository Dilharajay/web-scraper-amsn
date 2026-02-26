import pandas as pd
from bs4 import BeautifulSoup
import time
import random
import undetected_chromedriver as uc
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import re
from urllib.parse import unquote

# Download the VADER lexicon for Sentiment Analysis
nltk.download('vader_lexicon', quiet=True)
sia = SentimentIntensityAnalyzer()


def extract_asin(url):
    """Extracts the 10-character Amazon Standard Identification Number (ASIN) from messy URLs."""
    decoded_url = unquote(str(url))
    match = re.search(r'/(?:dp|product)/([A-Z0-9]{10})', decoded_url)
    return match.group(1) if match else None


def get_overall_sentiment(reviews_text):
    """Calculates an average sentiment score from a list of 10 text reviews."""
    if not reviews_text:
        return "No Reviews / Blocked"

    # Calculate the compound score (-1 to 1) for each individual review
    compound_scores = [sia.polarity_scores(str(text))['compound'] for text in reviews_text]

    # Average them out to find the overall sentiment of the product
    avg_score = sum(compound_scores) / len(compound_scores)

    if avg_score >= 0.05:
        return "Positive"
    elif avg_score <= -0.05:
        return "Negative"
    else:
        return "Neutral"


def scrape_all_sentiments():
    print("Loading 'amazon_products_link.csv'...")
    try:
        df = pd.read_csv("amazon_products_link.csv")
    except FileNotFoundError:
        print("Error: Ensure the dataset is in the same directory.")
        return

    # Create the new column as you requested
    df['Overall_Sentiment'] = "Pending"

    print("Initializing stealth browser...")
    options = uc.ChromeOptions()
    # Ensure this matches the Google Chrome version on your Ubuntu machine
    driver = uc.Chrome(options=options, version_main=145)

    try:
        # Loop through each row (all 88 products)
        for index, row in df.iterrows():
            title = str(row['title'])[:40]  # Snippet for clean terminal printing
            link = row['link']

            asin = extract_asin(link)
            if not asin:
                df.at[index, 'Overall_Sentiment'] = "Invalid Link"
                print(f"[{index + 1}/{len(df)}] Skipped (No ASIN): {title}...")
                continue

            # Generate a direct URL to the first page of reviews (roughly 10 reviews)
            reviews_url = f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews"

            print(f"\n[{index + 1}/{len(df)}] Scraping: {title}...")
            driver.get(reviews_url)

            # Vital sleep loop to prevent bot detection between the 88 requests
            time.sleep(random.uniform(4, 7))

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            review_blocks = soup.find_all("div", attrs={"data-hook": "review"})

            # Extract text from the review blocks
            reviews_text = []
            for block in review_blocks:
                text_element = block.find("span", attrs={"data-hook": "review-body"})
                if text_element:
                    reviews_text.append(text_element.text.strip())

            if not reviews_text:
                print(" -> 0 reviews found. (Product has no reviews or Amazon triggered a CAPTCHA)")
                df.at[index, 'Overall_Sentiment'] = "No Reviews / Blocked"
            else:
                # Calculate the sentiment and append it to the current row
                sentiment = get_overall_sentiment(reviews_text)
                print(f" -> Grabbed {len(reviews_text)} reviews. Sentiment: {sentiment}")
                df.at[index, 'Overall_Sentiment'] = sentiment

    except Exception as e:
        print(f"Script stopped due to an error: {e}")

    finally:
        print("\nClosing browser...")
        driver.quit()

    # Save the updated dataframe with the new column
    output_filename = "amazon_products_with_sentiment.csv"
    df.to_csv(output_filename, index=False)
    print(f"\nTask Complete! Updated dataset saved locally as '{output_filename}'")


if __name__ == "__main__":
    scrape_all_sentiments()