#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if network argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <network>"
    echo "Available networks:"
    for network_dir in "$SCRIPT_DIR/../configs"/*/; do
        if [ -d "$network_dir" ] && [[ "$(basename "$network_dir")" != *"-shared" ]]; then
            echo "  - $(basename "$network_dir")"
        fi
    done
    exit 1
fi

NETWORK="$1"
CONFIGS_DIR="$SCRIPT_DIR/../configs/$NETWORK"

# Check if network config directory exists
if [ ! -d "$CONFIGS_DIR" ]; then
    echo "Error: Network '$NETWORK' not found!"
        echo "Available networks:"
        for network_dir in "$SCRIPT_DIR/../configs"/*/; do
            if [ -d "$network_dir" ] && [[ "$(basename "$network_dir")" != *"-shared" ]]; then
                echo "  - $(basename "$network_dir")"
            fi
        done
        exit 1
fi

echo "Starting all $NETWORK price feed relayers..."

# Get all feed config files (excluding backup-template.toml and shared configs)
feeds=()
for config_file in "$CONFIGS_DIR"/*.toml; do
    if [[ -f "$config_file" ]]; then
        filename=$(basename "$config_file")
        # Skip backup-template and shared configs
        if [[ "$filename" != "backup-template.toml" && "$filename" != *"-shared.toml" ]]; then
            feed_name=$(basename "$config_file" .toml)
            feeds+=("$feed_name")
        fi
    fi
done

if [ ${#feeds[@]} -eq 0 ]; then
    echo "No feed configuration files found in $CONFIGS_DIR!"
    echo "Create .toml files for your feeds first."
    exit 1
fi

echo "Found ${#feeds[@]} feeds: ${feeds[*]}"
echo ""

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/../logs"

# Start each feed
for feed in "${feeds[@]}"; do
    echo "Starting $NETWORK-$feed..."
    
    # Create screen session name
    session_name="relayer-$NETWORK-$feed"
    
    # Start the relayer in a screen session
    screen -dmS "$session_name" bash -c "cd '$SCRIPT_DIR/..' && relayer --config configs/$NETWORK/$feed.toml relay-threshold --verbose --backup 2>&1 | tee -a logs/relayer-$NETWORK-$feed.log"
    
    sleep 2  # Small delay between starts
done

echo ""
echo "All $NETWORK feeds started! Use 'screen -ls' to see running sessions."
echo ""
echo "Useful commands:"
echo "  screen -ls                           # List all sessions"
echo "  screen -r relayer-$NETWORK-<feed>     # Attach to a specific feed"
echo "  screen -S relayer-$NETWORK-<feed> -X quit  # Stop a specific feed"
echo "  ./stop_all_feeds.sh $NETWORK         # Stop all $NETWORK feeds"
