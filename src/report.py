import pandas as pd
import matplotlib.pyplot as plt
import plotext as plt_term
import os
from dotenv import load_dotenv

load_dotenv()

def generate_power_report(csv_file="data/layer_data.csv", show_terminal_plot=False):
    # Read the CSV file
    df = pd.read_csv(csv_file)
    
    # Create the matplotlib plot
    plt.figure(figsize=(12, 6))
    plt.plot(df['height'], df['reporter_power'], '-b', linewidth=1)
    
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
        plt_term.plot(df['height'], df['reporter_power'], 
                    #  point_marker="dot",  # Use dots for data points
                    #  line_marker="·",     # Use smaller line markers
                     color="blue")        # Set line color
        
        # Customize appearance
        plt_term.title("Aggregate Report Power")
        plt_term.xlabel("Block Height")
        plt_term.ylabel("Power")
        plt_term.grid(True)              # Add grid
        plt_term.theme("dark")           # Use dark theme
        plt_term.show()
    
    # Print statistics
    stats = {
        'mean': df['reporter_power'].mean(),
        'median': df['reporter_power'].median(),
        'std_dev': df['reporter_power'].std(),
        'min': df['reporter_power'].min(),
        'max': df['reporter_power'].max()
    }
    
    print("\nAggregate Power Statistics:")
    for key, value in stats.items():
        print(f"{key}: {value:,.2f}")

    return stats

if __name__ == "__main__":
    generate_power_report() 