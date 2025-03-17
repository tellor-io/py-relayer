import pandas as pd
import matplotlib.pyplot as plt
import plotext as plt_term
import os
import json
from dotenv import load_dotenv

load_dotenv()

def generate_power_report(csv_file="data/layer_data.csv", show_terminal_plot=False):
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

    return stats

if __name__ == "__main__":
    generate_power_report() 