from src.layer_client import get_data_before, get_layer_connection_status, get_current_power_threshold
import os
from dotenv import load_dotenv
import csv
import json
import time

load_dotenv()

def scrape_layer(query_id, output_file, scrape_count):
    status, err = get_layer_connection_status()
    if err:
        print(f"layer_scraper: Error getting layer connection status: {err}")
        return
    print(f"layer_scraper: Layer connection status: {status}")
    
    # Get current power threshold
    power_threshold, err = get_current_power_threshold()
    if err:
        print(f"layer_scraper: Error getting power threshold: {err}")
        power_threshold = None
    else:
        print(f"layer_scraper: Power threshold: {power_threshold}")
    
    # Save metadata
    metadata_file = output_file.replace('.csv', '_metadata.json')
    metadata = {
        "query_id": query_id,
        "power_threshold": power_threshold,
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"layer_scraper: Saved metadata to {metadata_file}")
    
    scrape_layer_data(query_id, output_file, scrape_count)

def scrape_layer_data(query_id, output_file, scrape_count):
    csv_header = ["query_id", "aggregate_value", "aggregate_reporter", "reporter_power", "flagged", "index", "aggregate_report_index", "height", "micro_height", "timestamp"]
    print(f"layer_scraper: Scraping layer data to {output_file}")
    print(f"layer_scraper: Query ID: {query_id}")
    print(f"layer_scraper: Scrape count: {scrape_count}")
    # Initialize timestamp and count existing entries
    timestamp = 1000000000000000000  # default start
    existing_entries = 0
    
    if os.path.exists(output_file):
        with open(output_file, "r", newline="") as file:
            reader = csv.reader(file)
            next(reader)  # Skip header
            
            # Count existing entries and get most recent timestamp
            rows = list(reader)
            existing_entries = len(rows)
            
            if existing_entries > 0:
                timestamp = int(rows[0][-1])  # Get timestamp from first row (most recent entry)
                print(f"Found {existing_entries} existing entries")
                print(f"Resuming scrape from timestamp: {timestamp}")
            else:
                print("No existing data found, starting from beginning")
    else:
        # Write CSV header for new file
        with open(output_file, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(csv_header)
        print("Created new data file")

    # Calculate remaining data points needed
    remaining_points = scrape_count - existing_entries
    if remaining_points <= 0:
        print(f"Already have {existing_entries} entries, no additional data points needed")
        return
    
    print(f"Scraping {remaining_points} additional data points...")

    # Rest of the scraping logic, but only for remaining points
    for _ in range(remaining_points):
        data, err = get_data_before(query_id, timestamp)
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
            aggregate_data["aggregate_power"],
            aggregate_data["flagged"],
            aggregate_data["index"],
            aggregate_data["height"],
            aggregate_data["micro_height"],
            data["timestamp"]
        ]

        # Write data to the beginning of the CSV file
        with open(output_file, "r+", newline="") as file:
            reader = csv.reader(file)
            rows = list(reader)
            rows.insert(1, row_data)  # Insert after header
            file.seek(0)
            writer = csv.writer(file)
            writer.writerows(rows)

        # Update timestamp to the latest report timestamp
        timestamp = data["timestamp"]

    print(f"Scraped data saved to {output_file}")

# scrape_layer()
