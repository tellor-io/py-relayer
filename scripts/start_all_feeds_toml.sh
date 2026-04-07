#!/bin/bash

# Start all feeds for a specific network
# Usage: ./start_all_feeds_toml.sh <network> [--eth-private-key <key>]

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the absolute path to the py-relayer directory
RELAYER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
NETWORK=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --eth-private-key)
            export ETH_PRIVATE_KEY="$2"
            shift 2
            ;;
        --eth-private-key=*)
            export ETH_PRIVATE_KEY="${1#*=}"
            shift
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            if [ -z "$NETWORK" ]; then
                NETWORK="$1"
            fi
            shift
            ;;
    esac
done

# Check if network argument is provided
if [ -z "$NETWORK" ]; then
    echo "Usage: $0 <network> [--eth-private-key <key>]"
    echo "  --eth-private-key  Ethereum private key (can also be set via ETH_PRIVATE_KEY env var)"
    echo "Available networks:"
    for network_dir in "$RELAYER_DIR/configs"/*/; do
        if [ -d "$network_dir" ] && [[ "$(basename "$network_dir")" != *"-shared" ]]; then
            echo "  - $(basename "$network_dir")"
        fi
    done
    exit 1
fi

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
echo "[DEBUG] SCRIPT_DIR=$SCRIPT_DIR"
echo "[DEBUG] RELAYER_DIR=$RELAYER_DIR"
echo "[DEBUG] CONFIGS_DIR=$CONFIGS_DIR"
echo "[DEBUG] venv path=$RELAYER_DIR/env/bin/activate (exists: $([ -f "$RELAYER_DIR/env/bin/activate" ] && echo yes || echo NO))"
echo "[DEBUG] screen binary=$(command -v screen || echo NOT FOUND)"
echo "[DEBUG] ETH_PRIVATE_KEY set: $([ -n "$ETH_PRIVATE_KEY" ] && echo yes || echo NO)"
echo ""

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
    echo "[DEBUG] session_name=$session_name"
    echo "[DEBUG] config file=configs/$NETWORK/$feed.toml (exists: $([ -f "$RELAYER_DIR/configs/$NETWORK/$feed.toml" ] && echo yes || echo NO))"

    SCREEN_CMD="cd '$RELAYER_DIR' && source env/bin/activate && relayer --config configs/$NETWORK/$feed.toml relay-threshold --verbose 2>&1 | tee -a logs/relayer-$NETWORK-$feed.log; exec bash"
    echo "[DEBUG] screen command: screen -dmS \"$session_name\" bash -c \"$SCREEN_CMD\""

    # Start the relayer in a screen session (activate venv first)
    screen -dmS "$session_name" bash -c "$SCREEN_CMD"
    SCREEN_EXIT=$?
    echo "[DEBUG] screen exit code: $SCREEN_EXIT"

    sleep 1
    if screen -list | grep -q "$session_name"; then
        echo "[DEBUG] session '$session_name' confirmed running"
    else
        echo "[DEBUG] WARNING: session '$session_name' NOT found after start"
        echo "[DEBUG] Current screen sessions:"
        screen -list || true
    fi

    ((started++))
    sleep 1  # Small delay between starts
done

echo ""
echo "Started $started feeds, skipped $skipped (already running). Use 'screen -ls' to see running sessions."
echo ""
echo "Useful commands:"
echo "  screen -ls                           # List all sessions"
echo "  screen -r relayer-$NETWORK-<feed>     # Attach to a specific feed"
echo "  screen -S relayer-$NETWORK-<feed> -X quit  # Stop a specific feed"
echo "  ./stop_all_feeds.sh $NETWORK         # Stop all $NETWORK feeds"
