from src.layer_client import get_data_before, get_layer_connection_status, get_current_power_threshold, get_reports_by_aggregate
import os
from dotenv import load_dotenv
import csv
import json
import time
import pandas as pd
from src.logger_utils import get_logger

logger = get_logger(__name__)

load_dotenv()

def scrape_layer(query_id, output_file, scrape_count, scrape_micro):
    status, err = get_layer_connection_status()
    if err:
        logger.error(f"Error getting layer connection status: {err}")
        return
    logger.info(f"Layer connection status: {status}")
    
    # Get current power threshold
    power_threshold, err = get_current_power_threshold()
    if err:
        logger.error(f"Error getting power threshold: {err}")
        power_threshold = None
    else:
        logger.info(f"Power threshold: {power_threshold}")
    
    # Save metadata
    metadata_file = output_file.replace('.csv', '_metadata.json')
    metadata = {
        "query_id": query_id,
        "power_threshold": power_threshold,
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Saved metadata to {metadata_file}")
    
    scrape_layer_data(query_id, output_file, scrape_count)
    if scrape_micro:
        scrape_micro_reports(query_id,output_file)

def scrape_layer_data(query_id, output_file, scrape_count):
    csv_header = ["query_id", "aggregate_value", "aggregate_reporter", "reporter_power", "flagged", "index", "height", "micro_height", "timestamp"]
    logger.info(f"Scraping layer data to {output_file}")
    logger.info(f"Query ID: {query_id}")
    logger.info(f"Scrape count: {scrape_count}")
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
                logger.info(f"Found {existing_entries} existing entries")
                logger.info(f"Resuming scrape from timestamp: {timestamp}")
            else:
                logger.info("No existing data found, starting from beginning")
    else:
        # Write CSV header for new file
        with open(output_file, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(csv_header)
        logger.info("Created new data file")

    # Calculate remaining data points needed
    remaining_points = scrape_count - existing_entries
    if remaining_points <= 0:
        logger.info(f"Already have {existing_entries} entries, no additional data points needed")
        return
    
    logger.info(f"Scraping {remaining_points} additional data points...")

    # Rest of the scraping logic, but only for remaining points
    for _ in range(remaining_points):
        data, err = get_data_before(query_id, timestamp)
        if err:
            logger.error(f"Error getting data before {timestamp}: {err}")
            break

        logger.info(f"Data before {timestamp}: {data}")

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

    logger.info(f"Scraped data saved to {output_file}")

def scrape_micro_reports(query_id: str, aggregate_data_file: str, output_file: str = None):
    """Scrape micro reports for aggregates in aggregate_data_file"""
    logger.info(f"Scraping micro reports for {query_id} in {aggregate_data_file}")
    if output_file is None:
        output_file = aggregate_data_file.replace('.csv', '_micro.csv')
    logger.info(f"Output file: {output_file}")

    # Read the layer data
    df = pd.read_csv(aggregate_data_file)
    
    # Track which timestamps we've already processed
    processed_timestamps = set()
    if os.path.exists(output_file):
        micro_df = pd.read_csv(output_file)
        processed_timestamps = set(micro_df['timestamp'].unique())
        logger.info(f"Found {len(processed_timestamps)} already processed timestamps")
    
    # Setup output CSV if it doesn't exist
    headers = ['timestamp', 'aggregate_power', 'reporter', 'power', 'consecutive_reports']
    if not os.path.exists(output_file):
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
    
    # Track reporter streaks across all timestamps
    reporter_streaks = {}  # {reporter_address: current_streak}
    
    # Get latest streak counts from existing data if any
    if processed_timestamps:
        micro_df = pd.read_csv(output_file)
        latest_timestamp = micro_df['timestamp'].max()
        latest_reports = micro_df[micro_df['timestamp'] == latest_timestamp]
        for _, row in latest_reports.iterrows():
            reporter_streaks[row['reporter']] = row['consecutive_reports']
    
    # Process each unprocessed aggregate report
    unprocessed_df = df[~df['timestamp'].isin(processed_timestamps)].sort_values('timestamp', ascending=False)
    logger.info(f"Processing {len(unprocessed_df)} new aggregate reports")
    
    for _, row in unprocessed_df.iterrows():
        logger.info(f"Processing aggregate at timestamp {row['timestamp']}")
        timestamp = row['timestamp']
        aggregate_power = row['reporter_power']
        
        # Get micro reports for this aggregate
        micro_reports_response, err = get_reports_by_aggregate(query_id, int(timestamp))
        if err:
            logger.error(f"Error getting reports by aggregate: {err}")
            continue
            
        # Prepare all rows for this timestamp
        timestamp_rows = []
        participating_reporters = set()
        
        # Process each micro report
        for report in micro_reports_response['microReports']:
            reporter = report['reporter']
            participating_reporters.add(reporter)
            
            # Update streak
            if reporter in reporter_streaks:
                reporter_streaks[reporter] += 1
            else:
                reporter_streaks[reporter] = 1
                
            # Add row to batch
            timestamp_rows.append([
                timestamp,
                aggregate_power,
                reporter,
                report['power'],
                reporter_streaks[reporter]
            ])
        
        # Reset streaks for non-participating reporters
        for reporter in list(reporter_streaks.keys()):
            if reporter not in participating_reporters:
                reporter_streaks[reporter] = 0
        
        # Write all rows for this timestamp atomically
        with open(output_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(timestamp_rows)
        
        logger.info(f"Wrote {len(timestamp_rows)} micro reports for timestamp {timestamp}")
    
    logger.info(f"Micro report data saved to {output_file}")
