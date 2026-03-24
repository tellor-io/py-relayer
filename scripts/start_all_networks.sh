#!/bin/bash

# Start all feeds for all networks
# Usage: ./start_all_networks.sh

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting all feeds for all networks..."
echo ""

# Collect all network directories (excluding shared configs)
networks=()
for network_dir in "$SCRIPT_DIR/../configs"/*/; do
    if [ -d "$network_dir" ] && [[ "$(basename "$network_dir")" != *"-shared" ]]; then
        network_name=$(basename "$network_dir")
        networks+=("$network_name")
    fi
done

if [ ${#networks[@]} -eq 0 ]; then
    echo "No network directories found in configs!"
    exit 1
fi

echo "Found ${#networks[@]} networks: ${networks[*]}"
echo ""

# Process each network
for network in "${networks[@]}"; do
    echo "=========================================="
    echo "Processing network: $network"
    echo "=========================================="
    echo ""
    
    # First, stop all feeds for this network to avoid duplicates
    echo "Stopping existing feeds for $network..."
    "$SCRIPT_DIR/stop_all_feeds.sh" "$network"
    echo ""
    
    # Wait a moment for processes to fully stop
    sleep 2
    
    # Then start all feeds for this network
    echo "Starting all feeds for $network..."
    "$SCRIPT_DIR/start_all_feeds_toml.sh" "$network"
    echo ""
    
    # Small delay between networks
    sleep 3
done

echo ""
echo "=========================================="
echo "All networks processed!"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  screen -ls                           # List all sessions"
echo "  screen -r relayer-<network>-<feed>    # Attach to a specific feed"
echo "  screen -S relayer-<network>-<feed> -X quit  # Stop a specific feed"
echo "  ./stop_all_feeds.sh <network>         # Stop all feeds for a network"
echo "  ./stop_all_feeds.sh all               # Stop all feeds for all networks"
