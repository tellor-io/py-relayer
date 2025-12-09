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
    echo ""
    echo "Or use 'all' to stop all relayer sessions:"
    echo "  $0 all"
    exit 1
fi

NETWORK="$1"

echo "Stopping relayer feeds..."

if [ "$NETWORK" = "all" ]; then
    echo "Stopping ALL relayer sessions..."
    
    # Get all running relayer sessions
    sessions=$(screen -ls | grep "relayer-" | awk '{print $1}' | sed 's/.*\.//')
    
    if [ -z "$sessions" ]; then
        echo "No relayer sessions found."
        exit 0
    fi
    
    echo "Found sessions: $sessions"
    echo ""
    
    # Stop each session
    for session in $sessions; do
        echo "Stopping $session..."
        # Send Ctrl+C to stop the process gracefully
        screen -S "$session" -X stuff $'\003' 2>/dev/null
        sleep 1
        # Quit the screen session
        screen -S "$session" -X quit 2>/dev/null || echo "  Session $session not found or already stopped"
    done
    
    # Kill any remaining orphaned processes
    sleep 2
    pkill -f "relayer --config configs/.* relay-threshold" 2>/dev/null || true
    
    echo ""
    echo "All relayer sessions stopped."
    
else
    # Stop feeds for specific network
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
    
    echo "Stopping all $NETWORK feeds..."
    
    # Get all feed config files for the network
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
        echo "No feed configuration files found for $NETWORK!"
        exit 1
    fi
    
    echo "Found ${#feeds[@]} feeds: ${feeds[*]}"
    echo ""
    
    # Stop each feed
    for feed in "${feeds[@]}"; do
        session_name="relayer-$NETWORK-$feed"
        echo "Stopping $session_name..."
        # Send Ctrl+C to stop the process gracefully
        screen -S "$session_name" -X stuff $'\003' 2>/dev/null
        sleep 1
        # Quit the screen session
        screen -S "$session_name" -X quit 2>/dev/null || echo "  Session $session_name not found or already stopped"
    done
    
    # Kill any remaining orphaned processes for this network
    sleep 2
    pkill -f "relayer --config configs/$NETWORK/.* relay-threshold" 2>/dev/null || true
    
    echo ""
    echo "All $NETWORK feeds stopped."
fi

echo ""
echo "Remaining sessions:"
screen -ls | grep "relayer-" || echo "No relayer sessions running."

# Final cleanup: kill any remaining orphaned relayer processes
remaining_procs=$(pgrep -f "relayer --config configs/.* relay-threshold" 2>/dev/null || true)
if [ -n "$remaining_procs" ]; then
    echo ""
    echo "Found orphaned relayer processes, killing them..."
    pkill -f "relayer --config configs/.* relay-threshold" 2>/dev/null || true
    sleep 1
    # Also kill any remaining tee processes writing to relayer logs
    pkill -f "tee -a logs/relayer-.*\.log" 2>/dev/null || true
fi
