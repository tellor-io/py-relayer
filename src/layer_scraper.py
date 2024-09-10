from layer_client import get_data_before, get_layer_connection_status
import os
from dotenv import load_dotenv
import csv

load_dotenv()

QUERY_ID = os.getenv("QUERY_ID")
n_data_points = 1000
LAYER_DATA_CSV = "data/layer_data.csv"

def scrape_layer():
    status, err = get_layer_connection_status()
    if err:
        print(f"layer_scraper: Error getting layer connection status: {err}")
        return
    print(f"layer_scraper: Layer connection status: {status}")
    scrape_layer_data()

def scrape_layer_data():
    timestamp = 1000000000000000000
    csv_file = LAYER_DATA_CSV
    csv_header = ["query_id", "aggregate_value", "aggregate_reporter", "reporter_power", "standard_deviation",
                  "flagged", "index", "aggregate_report_index", "height", "micro_height", "timestamp"]

    # Write CSV header if the file doesn't exist
    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(csv_header)

    for _ in range(n_data_points):
        data, err = get_data_before(QUERY_ID, timestamp)
        if err:
            print(f"Error getting data before {timestamp}: {err}")
            break

        print(f"Data before {timestamp}: {data}")

        # Extract relevant data from the response
        aggregate_data = data["aggregate"]
        row_data = [
            aggregate_data["query_id"],
            aggregate_data["aggregate_value"],
            aggregate_data["aggregate_reporter"],
            aggregate_data["reporter_power"],
            aggregate_data["standard_deviation"],
            aggregate_data["flagged"],
            aggregate_data["index"],
            aggregate_data["aggregate_report_index"],
            aggregate_data["height"],
            aggregate_data["micro_height"],
            data["timestamp"]
        ]

        # Write data to the beginning of the CSV file
        with open(csv_file, "r+", newline="") as file:
            reader = csv.reader(file)
            rows = list(reader)
            rows.insert(1, row_data)
            file.seek(0)
            writer = csv.writer(file)
            writer.writerows(rows)

        # Update timestamp to the latest report timestamp
        timestamp = data["timestamp"]

    print(f"Scraped data saved to {csv_file}")

scrape_layer()
