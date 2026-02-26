import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import time
import random
import undetected_chromedriver as uc
import sys
import select
import datetime
import re
import os


def get_title(soup):
    try:
        title = soup.find("span", attrs={"id": "productTitle"})
        title_val = title.text
        title_str = title_val.strip()
    except AttributeError:
        title_str = ""
    return title_str


def get_price(soup):
    try:
        price = soup.find("span", attrs={"class": "a-price aok-align-center apex-pricetopay-value"})
        price_val = price.find("span", attrs={"class": "a-offscreen"}).text
        price_str = price_val.strip()
    except AttributeError:
        price_str = "Not Available"
    return price_str


def get_rating(soup):
    try:
        rating = soup.find("span", attrs={"class": "a-icon-alt"})
        rating_val = rating.text
        rating_str = rating_val.strip()
    except AttributeError:
        rating_str = ""
    return rating_str


def clean_price(price_str):
    if pd.isna(price_str) or "Not Available" in str(price_str):
        return None
    # Remove currency symbol (LKR, $, etc) and commas
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(cleaned)
    except ValueError:
        return None


if __name__ == "__main__":

    load_dotenv()

    # Initialize the dictionary to store data
    data_dict = {"timestamp": [], "title": [], "price": [], "rating": [], "link": []}

    print("Initializing stealth browser...")
    options = uc.ChromeOptions()
    # options.add_argument('--headless')

    # Initialize the browser ONCE outside the loop
    driver = uc.Chrome(options=options, version_main=145)

    try:
        for page_num in range(1, 4):

            if page_num == 1:
                URL = 'https://www.amazon.com/s?k=ram&crid=267ZPYDO2S92W&sprefix=ra%2Caps%2C450&ref=nb_sb_noss_2'
            else:
                URL = f"https://www.amazon.com/s?k=ram&page={page_num}&xpid=eKUToY2lUp68L&crid=267ZPYDO2S92W&qid=1772094492&sprefix=ra%2Caps%2C450&ref=sr_pg_{page_num}"

            print(f"\n--- Scraping Search Page {page_num} ---")

            # Navigate using the browser
            driver.get(URL)

            # Wait for the search page to load
            time.sleep(random.uniform(3, 5))

            # Grab the fully rendered HTML from the browser
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Fetch links as Lists of Tag Objects
            links = soup.find_all("a", attrs={
                "class": "a-link-normal s-line-clamp-2 puis-line-clamp-3-for-col-4-and-8 s-link-style a-text-normal"})

            # Store Links
            links_list = []
            print("Extracting links from the page...")

            for link in links:
                links_list.append(link.get('href'))

            print(f"Total number of products found on page {page_num}: {len(links_list)}\n")

            # Loop for extracting product details from each link
            for link in links_list:
                # Handle relative vs absolute links safely
                full_link = link if link.startswith('http') else "https://www.amazon.com" + link

                driver.get(full_link)

                # Wait for the product page to load BEFORE grabbing the HTML
                sleep_time = random.uniform(2, 4)
                print(f"Sleeping for {sleep_time:.2f} seconds to mimic human behavior...")
                time.sleep(sleep_time)

                # Grab the HTML of the specific product page
                new_soup = BeautifulSoup(driver.page_source, 'html.parser')

                data_dict["title"].append(get_title(new_soup))
                data_dict["price"].append(get_price(new_soup))
                data_dict["rating"].append(get_rating(new_soup))
                data_dict["link"].append(full_link)
                data_dict["timestamp"].append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    except Exception as e:
        print(f"\nScript stopped due to an error: {e}")

    finally:
        # This guarantees the browser closes, even if you press Ctrl+C to stop the script
        print("\nClosing the browser...")
        driver.quit()

    # Create DataFrame
    amazon_df = pd.DataFrame(data_dict)
    print(amazon_df.head())

    # Save to CSV
    is_saved = False
    default_filename = "amazon_products_link_v2.csv"

    while not is_saved:
        print(f"\nDo you want to save the scraped data? (y/n): \ndata will be automatically saved in 20 seconds")

        # Wait for terminal input for exactly 20 seconds
        ready, _, _ = select.select([sys.stdin], [], [], 20)

        if ready:
            # User types something before 20 seconds
            response = sys.stdin.readline().strip().lower()
        else:
            # No input within 20 seconds passed
            print("\nTimeout reached. Automatically saving data....")
            response = 'y'

        if response == 'n':
            print("\nDataframe not saved")
            break


        elif response == 'y' or response == '':

            # If the user manually typed 'y' (ready is True), ask for a custom filename

            if ready:
                custom_name = input(f"\nEnter a file name (or press Enter to use '{default_filename}'): ").strip()
                if custom_name:
                    # Automatically append .csv if you forget to type it
                    if not custom_name.endswith('.csv'):
                        custom_name += '.csv'
                    filename = custom_name
                else:
                    filename = default_filename
            # If it timed out, bypass the input and use the default
            else:
                filename = default_filename

            try:
                # Check for existing data and compare prices
                if os.path.exists(filename):
                    print(f"\nFile '{filename}' exists. Checking for price drops...")
                    try:
                        history_df = pd.read_csv(filename)

                        # Clean prices for comparison
                        amazon_df['price_val'] = amazon_df['price'].apply(clean_price)
                        history_df['price_val'] = history_df['price'].apply(clean_price)

                        # Get the latest price from history for each link
                        # We sort by timestamp descending and drop duplicates to get the last recorded price
                        # Assuming 'timestamp' column exists in history
                        if 'timestamp' in history_df.columns:
                            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
                            latest_history = history_df.sort_values('timestamp', ascending=False).drop_duplicates(
                                'link')
                        else:
                            # If no timestamp, just take the last occurrence
                            latest_history = history_df.drop_duplicates('link', keep='last')

                        # Merge to compare
                        merged = pd.merge(amazon_df, latest_history[['link', 'price_val', 'title']], on='link',
                                          how='inner', suffixes=('_new', '_old'))

                        # Find drops
                        drops = merged[merged['price_val_new'] < merged['price_val_old']]

                        if not drops.empty:
                            print("\nPRICE DROP ALERTS")
                            for _, row in drops.iterrows():
                                drop_amt = row['price_val_old'] - row['price_val_new']
                                print(f"Price Drop for: {row['title_new'][:50]}...")
                                print(
                                    f"  Old Price: {row['price_val_old']} -> New Price: {row['price_val_new']} (Drop: {drop_amt:.2f})")
                                print(f"  Link: {row['link']}\n")
                        else:
                            print("No price drops detected compared to the last record.")

                        # Clean up temporary column
                        amazon_df.drop(columns=['price_val'], inplace=True)

                    except Exception as e:
                        print(f"Could not analyze history: {e}")

                    # Append to file
                    amazon_df.to_csv(filename, mode='a', header=False, index=False)
                    print(f"\nData appended to '{filename}'.")

                else:
                    # Create new file
                    amazon_df.to_csv(filename, index=False)
                    print(f"\nDataframe successfully saved as '{filename}'.")

                print(f"Dataframe has {amazon_df.shape[0]} rows and {amazon_df.shape[1]} columns.")
                print("\nDataframe missing values:")
                print(amazon_df.isnull().sum())
                is_saved = True

            except Exception as e:
                print(f"\nError saving the dataframe: {e}")
                retry = input("Try again? (y/n): ").strip().lower()
                if retry != 'y':
                    print("\nAborting save.")
                    break
        else:
            print("\nInvalid input. Please enter 'y' or 'n'.")
