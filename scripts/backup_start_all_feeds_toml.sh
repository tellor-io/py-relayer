#!/bin/bash

# Backup and start all feeds for a specific network
# Usage: ./backup_start_all_feeds_toml.sh <network>

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the absolute path to the py-relayer directory
RELAYER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check if network argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <network>"
    echo "Available networks:"
    for network_dir in "$RELAYER_DIR/configs"/*/; do
        if [ -d "$network_dir" ] && [[ "$(basename "$network_dir")" != *"-shared" ]]; then
            echo "  - $(basename "$network_dir")"
        fi
    done
    exit 1
fi

NETWORK="$1"
CONFIGS_DIR="$RELAYER_DIR/configs/$NETWORK"

# Check if network config directory exists
if [ ! -d "$CONFIGS_DIR" ]; then
    echo "Error: Network '$NETWORK' not found!"
        echo "Available networks:"
        for network_dir in "$RELAYER_DIR/configs"/*/; do
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
mkdir -p "$RELAYER_DIR/logs"

# Start each feed
started=0
skipped=0
for feed in "${feeds[@]}"; do
    # Create screen session name
    session_name="relayer-$NETWORK-$feed"
    
    # Check if session already exists
    if screen -list | grep -q "$session_name"; then
        echo "Skipping $NETWORK-$feed (already running)"
        ((skipped++))
        continue
    fi
    
    echo "Starting $NETWORK-$feed..."
    
    # Start the relayer in a screen session (activate venv first)
    screen -dmS "$session_name" bash -c "cd '$RELAYER_DIR' && source env/bin/activate && relayer --config configs/$NETWORK/$feed.toml relay-threshold --verbose --backup 2>&1 | tee -a logs/relayer-$NETWORK-$feed.log"
    
    ((started++))
    sleep 2  # Small delay between starts
done

echo ""
echo "Started $started feeds, skipped $skipped (already running). Use 'screen -ls' to see running sessions."
echo ""
echo "Useful commands:"
echo "  screen -ls                           # List all sessions"
echo "  screen -r relayer-$NETWORK-<feed>     # Attach to a specific feed"
echo "  screen -S relayer-$NETWORK-<feed> -X quit  # Stop a specific feed"
echo "  ./stop_all_feeds.sh $NETWORK         # Stop all $NETWORK feeds"
