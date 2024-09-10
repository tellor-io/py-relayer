from evm_client import init_web3, get_value_count, get_price_data_by_index
import os
from dotenv import load_dotenv
import numpy as np
import matplotlib.pyplot as plt
import csv

load_dotenv()

QUERY_ID = os.getenv("QUERY_ID")
CSV_FILE = "data/price_data.csv"

def start_scraper():
    print("scraper: Starting scraper...")

    print("scraper: Initializing web3...")
    init_web3()
    
    print("scraper: Getting value count...")
    value_count = get_value_count()
    # value_count = 400
    print("scraper: Value count: ", value_count)

    # Check existing data in CSV
    existing_data_count = 0
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r") as file:
            existing_data_count = sum(1 for _ in csv.reader(file)) - 1  # Subtract 1 for header row

    print("scraper: Existing data count in CSV: ", existing_data_count)

    if value_count > existing_data_count:
        print("scraper: Getting new price data...")
        new_price_data_array = []
        for i in range(existing_data_count, value_count):
            price_data = get_price_data_by_index(i)
            new_price_data_array.append(price_data)
            print(f"scraper: Price data for index {i}: ", price_data)

        # Append new data to CSV
        with open(CSV_FILE, "a", newline="") as file:
            writer = csv.writer(file)
            for data in new_price_data_array:
                writer.writerow(data)
    else:
        print("scraper: No new data to scrape.")

    # Read all data from CSV
    price_data_array = []
    with open(CSV_FILE, "r") as file:
        reader = csv.reader(file)
        next(reader)  # Skip header row
        for row in reader:
            price_data_array.append(tuple(map(int, row)))

    print(f"scraper: Value count: {len(price_data_array)}")
    # Remove outliers
    relay_timestamp_diffs = [data[5] - data[1] // 1000 for data in price_data_array]
    Q1 = np.percentile(relay_timestamp_diffs, 25)
    Q3 = np.percentile(relay_timestamp_diffs, 75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 3 * IQR
    upper_bound = Q3 + 3 * IQR
    print(f"scraper: Q1: {Q1}, Q3: {Q3}, IQR: {IQR}, lower_bound: {lower_bound}, upper_bound: {upper_bound}")
    relay_timestamp_diffs_filtered = [x for x in relay_timestamp_diffs if lower_bound <= x <= upper_bound]
    # relay_timestamp_diffs_filtered = relay_timestamp_diffs

    num_outliers = len(relay_timestamp_diffs) - len(relay_timestamp_diffs_filtered)
    print(f"scraper: Number of outliers found: {num_outliers}")

    # Generate statistics
    avg_diff = np.mean(relay_timestamp_diffs_filtered)
    median_diff = np.median(relay_timestamp_diffs_filtered)
    max_diff = np.max(relay_timestamp_diffs_filtered)
    min_diff = np.min(relay_timestamp_diffs_filtered)
    print(f"scraper: Average relay timestamp difference: {avg_diff}")
    print(f"scraper: Median relay timestamp difference: {median_diff}")
    print(f"scraper: Maximum relay timestamp difference: {max_diff}")
    print(f"scraper: Minimum relay timestamp difference: {min_diff}")

    # Chart the data
    plt.figure(figsize=(10, 6))
    plt.plot(relay_timestamp_diffs_filtered)
    plt.xlabel("Data Index")
    plt.ylabel("Relay Timestamp Difference")
    plt.title("Relay Timestamp Difference vs Data Index (Outliers Removed)")
    plt.grid(True)
    plt.show()

start_scraper()
