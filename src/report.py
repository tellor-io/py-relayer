import pandas as pd
import matplotlib.pyplot as plt
import plotext as plt_term
import os
import json
from dotenv import load_dotenv

load_dotenv()

def generate_power_report(csv_file="data/layer_data.csv", show_terminal_plot=False, micro_report=False):
    # Read the CSV file
    df = pd.read_csv(csv_file)
    
    # Try to load metadata for power threshold
    metadata_file = csv_file.replace('.csv', '_metadata.json')
    power_threshold = None
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                power_threshold = metadata.get("power_threshold")
                # Ensure power_threshold is a number
                if power_threshold is not None:
                    power_threshold = float(power_threshold)
        except Exception as e:
            print(f"Error reading metadata: {e}")
    
    # Create the matplotlib plot
    plt.figure(figsize=(12, 6))
    plt.plot(df['height'], df['reporter_power'], '-b', linewidth=1)
    
    # Add power threshold line if available
    if power_threshold is not None:
        plt.axhline(y=power_threshold, color='r', linestyle='--', label=f'Power Threshold ({power_threshold})')
        plt.legend()
    
    # Customize the plot
    plt.title('Aggregate Reporter Power vs Block Height')
    plt.xlabel('Block Height')
    plt.ylabel('Aggregate Power')
    plt.grid(True)
    
    # Save the plot
    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(f"{output_dir}/power_vs_height.png")
    plt.close()

    # Generate terminal plot if requested
    if show_terminal_plot:
        plt_term.clear_terminal()
        # Set smaller size
        plt_term.plot_size(70, 20)
        
        # Plot with customizations
        plt_term.plot(df['height'].tolist(), df['reporter_power'].tolist(), color="blue")
        
        # Add power threshold line if available
        if power_threshold is not None:
            # Ensure power_threshold is a number
            plt_term.hline(float(power_threshold), color="red")
            
            # # Add a text label for the threshold
            # x_range = plt_term.xlim()
            # x_pos = x_range[0] + (x_range[1] - x_range[0]) * 0.75  # Position at 75% of x-axis
            # plt_term.text(f"Threshold: {power_threshold}", x_pos, power_threshold, color="red")
        
        # Customize appearance
        plt_term.title("Aggregate Report Power")
        plt_term.xlabel("Block Height")
        plt_term.ylabel("Power")
        plt_term.grid(False)
        plt_term.theme("dark")
        plt_term.canvas_color("black")
        plt_term.ticks_color("bright_yellow")
        plt_term.show()
    
    # Calculate power statistics
    stats = {
        'mean': df['reporter_power'].mean(),
        'median': df['reporter_power'].median(),
        'std_dev': df['reporter_power'].std(),
        'min': df['reporter_power'].min(),
        'max': df['reporter_power'].max(),
        'report_count': len(df)
    }
    
    # Add power threshold statistics if available
    if power_threshold is not None:
        pct_consensus_threshold = (len(df[df['reporter_power'] >= power_threshold]) / len(df)) * 100
        stats['consensus_pct'] = pct_consensus_threshold
    
    print("\nAggregate Power Statistics:")
    for key, value in stats.items():
        if 'pct' in key:
            print(f"{key}: {value:.2f}%")
        else:
            print(f"{key}: {value:,.2f}")

    # Generate micro report if requested
    if micro_report:
        micro_csv = csv_file.replace('.csv', '_micro.csv')
        if os.path.exists(micro_csv):
            generate_micro_report(micro_csv)
        else:
            print(f"\nNo micro report data found at {micro_csv}")
    
    return stats

def generate_micro_report(micro_csv_file):
    """Analyze micro reports data and generate participation statistics"""
    df = pd.read_csv(micro_csv_file)
    
    # Get unique reporters and their first appearance timestamps
    reporter_first_seen = df.groupby('reporter')['timestamp'].min().to_dict()
    
    # Calculate participation stats for each reporter
    reporter_stats = {}
    
    for reporter in reporter_first_seen:
        # Get total number of aggregate reports since this reporter's first appearance
        reporter_start_time = reporter_first_seen[reporter]
        total_possible_reports = len(df[df['timestamp'] >= reporter_start_time].groupby('timestamp'))
        
        # Get actual number of reports from this reporter
        reporter_reports = len(df[
            (df['reporter'] == reporter) & 
            (df['timestamp'] >= reporter_start_time)
        ])
        
        # Get reporter's power (assuming constant throughout period)
        reporter_power = df[df['reporter'] == reporter]['power'].iloc[0]
        
        # Calculate participation rate
        participation_rate = reporter_reports / total_possible_reports
        
        reporter_stats[reporter] = {
            'participation_rate': participation_rate,
            'total_reports': reporter_reports,
            'total_possible': total_possible_reports,
            'power': reporter_power
        }
    
    # Print participation stats
    print("\nReporter Participation Statistics:")
    print(f"{'Reporter':<45} {'Power':<8} {'Rate':>6} {'Reports':>8} {'Possible':>10}")
    print("-" * 80)
    
    # Sort by power (descending) then participation rate (descending)
    sorted_reporters = sorted(
        reporter_stats.items(),
        key=lambda x: (-x[1]['power'], -x[1]['participation_rate'])
    )
    
    for reporter, stats in sorted_reporters:
        print(f"{reporter:<45} {stats['power']:<8} {stats['participation_rate']:>6.2%} "
              f"{stats['total_reports']:>8} {stats['total_possible']:>10}")
    
    return reporter_stats

if __name__ == "__main__":
    generate_power_report() 