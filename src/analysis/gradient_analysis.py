import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import seaborn as sns
from scipy import stats
import re
import os
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

def process_cost_function(temp_file, stress_file, name):
    """
    Process temperature and stress data files to calculate thermal gradient metrics.
    Includes enhanced unit detection, conversion, and robust error handling.
    
    Parameters:
    -----------
    temp_file : str
        Path to the temperature data file
    stress_file : str
        Path to the stress data file
    name : str
        Name identifier for this cost function
        
    Returns:
    --------
    metrics : dict
        Dictionary of calculated metrics
    arrays : dict
        Dictionary of processed data arrays for visualization
    """
    print(f"\nProcessing data for: {name}")
    print(f"Temperature file: {temp_file}")
    print(f"Stress file: {stress_file}")
    
    # Check if files exist
    if not os.path.exists(temp_file):
        print(f"ERROR: Temperature file not found: {temp_file}")
        return {}, {}
    if not os.path.exists(stress_file):
        print(f"ERROR: Stress file not found: {stress_file}")
        return {}, {}
    
    # Read temperature and stress text files (adjust delimiter if needed)
    try:
        df_temp = pd.read_csv(temp_file, delimiter='\t', encoding='latin1')
        df_stress = pd.read_csv(stress_file, delimiter='\t', encoding='latin1')
    except Exception as e:
        print(f"Error reading files: {e}")
        # Return empty dictionaries to avoid breaking the rest of the code
        return {}, {}
    
    # Clean header names: strip extra spaces and remove BOM if present
    df_temp.columns = df_temp.columns.str.strip().str.replace('\ufeff', '')
    df_stress.columns = df_stress.columns.str.strip().str.replace('\ufeff', '')
    
    print(f"Number of rows in temperature file: {len(df_temp)}")
    print(f"Number of rows in stress file: {len(df_stress)}")
    print(f"Temperature file columns: {df_temp.columns.tolist()}")
    print(f"Stress file columns: {df_stress.columns.tolist()}")
    
    # Function to find columns based on partial name match
    def find_column(df, pattern, default=None):
        matches = [col for col in df.columns if re.search(pattern, col, re.IGNORECASE)]
        if matches:
            return matches[0]
        print(f"WARNING: No column matching '{pattern}' found.")
        return default
    
    # Find relevant columns in temperature file
    temp_node_col = find_column(df_temp, r"node.*number")
    temp_x_col = find_column(df_temp, r"x.*location")
    temp_y_col = find_column(df_temp, r"y.*location")
    temp_z_col = find_column(df_temp, r"z.*location")
    temp_val_col = find_column(df_temp, r"temperature")
    
    # Find relevant columns in stress file
    stress_node_col = find_column(df_stress, r"node.*number")
    stress_x_col = find_column(df_stress, r"x.*location")
    stress_y_col = find_column(df_stress, r"y.*location")
    stress_z_col = find_column(df_stress, r"z.*location")
    stress_val_col = find_column(df_stress, r"(von.*mises|equivalent).*stress", "Equivalent (von-Mises) Stress")
    
    # Check if we found all required columns
    required_cols = {
        "Temperature node": temp_node_col,
        "Temperature X": temp_x_col,
        "Temperature Y": temp_y_col,
        "Temperature Z": temp_z_col,
        "Temperature value": temp_val_col,
        "Stress node": stress_node_col,
        "Stress X": stress_x_col,
        "Stress Y": stress_y_col,
        "Stress Z": stress_z_col,
        "Stress value": stress_val_col
    }
    
    missing_cols = [name for name, col in required_cols.items() if col is None]
    if missing_cols:
        print(f"ERROR: Missing required columns: {missing_cols}")
        print("Temperature columns:", df_temp.columns.tolist())
        print("Stress columns:", df_stress.columns.tolist())
        return {}, {}
    
    # Detect units and prepare for conversion
    def detect_unit(col_name):
        if isinstance(col_name, str):
            if re.search(r'\(mm\)', col_name, re.IGNORECASE):
                return 'mm'
            elif re.search(r'\(m\)', col_name, re.IGNORECASE):
                return 'm'
            elif re.search(r'\(MPa\)', col_name, re.IGNORECASE):
                return 'MPa'
            elif re.search(r'\(Pa\)', col_name, re.IGNORECASE):
                return 'Pa'
        return None
    
    # Detect units
    temp_x_unit = detect_unit(temp_x_col)
    stress_val_unit = detect_unit(stress_val_col)
    
    print(f"Detected units - Coordinates: {temp_x_unit}, Stress: {stress_val_unit}")
    
    # Rename columns to standardized names for merging
    df_temp = df_temp.rename(columns={
        temp_node_col: "Node Number",
        temp_x_col: "X Location",
        temp_y_col: "Y Location",
        temp_z_col: "Z Location",
        temp_val_col: "Temperature"
    })
    
    df_stress = df_stress.rename(columns={
        stress_node_col: "Node Number",
        stress_x_col: "X Location",
        stress_y_col: "Y Location",
        stress_z_col: "Z Location",
        stress_val_col: "Stress"
    })
    
    # Merge on "Node Number"
    df_merged = pd.merge(df_temp, df_stress, on="Node Number", how="inner", suffixes=('_temp', '_stress'))
    print(f"Number of rows after merging: {len(df_merged)}")
    
    # Check if the merge worked properly
    if len(df_merged) == 0:
        print("ERROR: No rows after merging. Check Node Number compatibility.")
        return {}, {}
    
    # Extract coordinate, temperature, and stress arrays using the first set of coordinates
    # (assuming temperature and stress are mapped to the same mesh)
    x = df_merged["X Location_temp"].values
    y = df_merged["Y Location_temp"].values
    z = df_merged["Z Location_temp"].values
    T = df_merged["Temperature"].values
    stress = df_merged["Stress"].values
    
    # Apply unit conversions if needed
    if temp_x_unit == 'mm':
        print("Converting coordinates from mm to m")
        x = x * 0.001  # Convert mm to m
        y = y * 0.001  # Convert mm to m
        z = z * 0.001  # Convert mm to m
    
    if stress_val_unit == 'MPa':
        print("Converting stress from MPa to Pa")
        stress = stress * 1000000  # Convert MPa to Pa
    
    # Check unique z values to determine if we need 3D analysis
    unique_z = np.unique(z)
    is_3d = len(unique_z) > 1
    print(f"Unique Z values: {len(unique_z)}")
    print(f"3D analysis required: {is_3d}")
    
    # For 2.5D chiplets, we'll focus on the main plane
    if is_3d:
        # Find the most common z-value (likely the top surface of the chiplet)
        z_counts = pd.Series(z).value_counts()
        main_z = z_counts.index[0]
        print(f"Using main Z plane at z = {main_z}")
        # Filter points to include only the main plane
        mask = (z == main_z)
        x = x[mask]
        y = y[mask]
        T = T[mask]
        stress = stress[mask]
    
    # Basic data checks
    print(f"Temperature range: {np.min(T):.2f} to {np.max(T):.2f} °C")
    print(f"Stress range: {np.min(stress):.2e} to {np.max(stress):.2e} Pa")
    
    # Check for sufficient data points
    if len(x) < 10:  # Arbitrary threshold
        print("ERROR: Insufficient data points for analysis")
        return {}, {}
    
    # Interpolate scattered data onto a regular grid
    num_points = 5000  # adjust as needed
    xi = np.linspace(x.min(), x.max(), num_points)
    yi = np.linspace(y.min(), y.max(), num_points)
    xi, yi = np.meshgrid(xi, yi)
    
    Ti = griddata((x, y), T, (xi, yi), method='linear')
    stress_i = griddata((x, y), stress, (xi, yi), method='linear')
    
    # Compute grid spacing (assuming uniform grid)
    dx = (xi[0, -1] - xi[0, 0]) / (num_points - 1)
    dy = (yi[-1, 0] - yi[0, 0]) / (num_points - 1)
    
    # Compute the temperature gradient using finite differences
    dT_dx, dT_dy = np.gradient(Ti, dx, dy)
    grad_T = np.sqrt(dT_dx**2 + dT_dy**2)  # ‖∇T‖
    
    # Calculate gradient direction (for visualization)
    grad_dir = np.arctan2(dT_dy, dT_dx) * 180 / np.pi  # in degrees
    
    # Temperature Gradient Uniformity Metrics
    std_grad = np.nanstd(grad_T)
    mean_grad = np.nanmean(grad_T)
    max_grad = np.nanmax(grad_T)
    severity_index = max_grad / mean_grad
    Tmax = np.nanmax(Ti)
    Tavg = np.nanmean(Ti)
    hotspot_intensity = (Tmax - Tavg) / Tavg
    
    # Stress-Temperature Correlation Metrics
    grad_T_flat = grad_T.flatten()
    stress_flat = stress_i.flatten()
    mask = ~np.isnan(grad_T_flat) & ~np.isnan(stress_flat)
    grad_T_clean = grad_T_flat[mask]
    stress_clean = stress_flat[mask]
    
    # Calculate correlation coefficient
    if len(grad_T_clean) > 0:
        corr_matrix = np.corrcoef(grad_T_clean, stress_clean)
        corr_coeff = corr_matrix[0, 1]
        
        # Calculate Spearman rank correlation (less sensitive to outliers)
        spearman_corr, _ = stats.spearmanr(grad_T_clean, stress_clean)
    else:
        corr_coeff = np.nan
        spearman_corr = np.nan
    
    # Calculate normalized coupling factor (stress/gradient)
    coupling_factor = stress_clean / (grad_T_clean + 1e-10)  # avoid division by zero
    coupling_mean = np.nanmean(coupling_factor)
    coupling_std = np.nanstd(coupling_factor)
    coupling_cv = coupling_std / coupling_mean  # coefficient of variation
    
    # Calculate spatial uniformity of stress
    stress_std = np.nanstd(stress_i)
    stress_mean = np.nanmean(stress_i)
    stress_cv = stress_std / stress_mean  # coefficient of variation for stress
    
    # Calculate gradient distribution metrics
    p10 = np.nanpercentile(grad_T, 10)
    p90 = np.nanpercentile(grad_T, 90)
    gradient_range_ratio = p90 / (p10 + 1e-10)
    
    # Create a metrics dictionary
    metrics = {
        "Standard Deviation (σ∇T)": std_grad,
        "Mean Temperature Gradient": mean_grad,
        "Max Temperature Gradient": max_grad,
        "Thermal Gradient Severity Index (Max/Mean)": severity_index,
        "Hotspot Intensity Factor ((Tmax-Tavg)/Tavg)": hotspot_intensity,
        "Gradient-Stress Correlation Coefficient (r)": corr_coeff,
        "Gradient-Stress Spearman Correlation": spearman_corr,
        "Local Thermal-Mechanical Coupling Factor - Mean": coupling_mean,
        "Local Thermal-Mechanical Coupling Factor - Std Dev": coupling_std,
        "Local Thermal-Mechanical Coupling Factor - CV": coupling_cv,
        "Stress Coefficient of Variation": stress_cv,
        "Gradient 90th/10th Percentile Ratio": gradient_range_ratio,
        "Maximum Temperature (°C)": Tmax,
        "Average Temperature (°C)": Tavg,
        "Maximum Stress (Pa)": np.nanmax(stress_i),
        "Average Stress (Pa)": stress_mean
    }
    
    # Create arrays dictionary for visualization
    arrays = {
        "xi": xi,
        "yi": yi,
        "Temperature Field": Ti,
        "Temperature Gradient": grad_T,
        "dT_dx": dT_dx,
        "dT_dy": dT_dy,
        "Temperature Gradient Direction": grad_dir,
        "Stress Field": stress_i,
        "Coupling Field": np.divide(stress_i, grad_T, out=np.full_like(stress_i, np.nan), where=grad_T != 0)
    }
    
    print(f"Processing complete for: {name}")
    print(f"Key metrics:")
    print(f"  - Temperature gradient std dev: {std_grad:.2f}")
    print(f"  - Thermal gradient severity index: {severity_index:.2f}")
    print(f"  - Gradient-Stress correlation: {corr_coeff:.2f}")
    print(f"  - Stress coefficient of variation: {stress_cv:.2f}")
    
    return metrics, arrays

def create_normalized_bar_chart(valid_names, valid_metrics, key_metrics, output_file="normalized_metrics_comparison.png"):
    """
    Create an improved bar chart with each metric separately normalized for better visibility.
    
    Parameters:
    -----------
    valid_names : list
        List of optimization approach names
    valid_metrics : list
        List of metric dictionaries
    key_metrics : list
        List of key metric names to include
    output_file : str
        Output file name
    """
    # Create subplots for each metric
    fig, axes = plt.subplots(1, len(key_metrics), figsize=(16, 6))
    
    # Ensure axes is always an array
    if len(key_metrics) == 1:
        axes = [axes]
    
    # Set a consistent color palette
    colors = plt.cm.tab10(range(len(valid_names)))
    
    for i, metric in enumerate(key_metrics):
        values = [metrics.get(metric, np.nan) for metrics in valid_metrics]
        
        # Skip if all values are NaN
        if all(np.isnan(v) for v in values):
            axes[i].text(0.5, 0.5, "No data", ha='center', va='center', transform=axes[i].transAxes)
            axes[i].set_title(metric)
            continue
            
        # Create bar plot
        bars = axes[i].bar(valid_names, values, color=colors)
        
        # Set descriptive title with shorter display name
        display_name = metric.split('(')[0].strip()
        axes[i].set_title(display_name, fontsize=11)
        
        # Add grid for readability
        axes[i].grid(axis='y', linestyle='--', alpha=0.3)
        
        # Rotate x-tick labels for better readability
        axes[i].tick_params(axis='x', rotation=45, labelsize=9)
        
        # Add value labels on bars
        for bar, val in zip(bars, values):
            if not np.isnan(val):
                height = val
                axes[i].text(bar.get_x() + bar.get_width()/2, 
                            height + (abs(max(values, key=abs) if values else 0) * 0.02), 
                            f'{val:.3f}', 
                            ha='center', va='bottom', fontsize=8)
    
    # Adjust layout and save
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Normalized bar chart saved to {output_file}")
    return fig

def create_individual_metric_comparisons(valid_names, valid_metrics, output_prefix="metric_comparison"):
    """
    Create individual comparison charts for different groups of related metrics.
    
    Parameters:
    -----------
    valid_names : list
        List of optimization approach names
    valid_metrics : list
        List of metric dictionaries
    output_prefix : str
        Prefix for output file names
    """
    # Define metric groups
    metric_groups = {
        "gradient_metrics": [
            "Standard Deviation (σ∇T)",
            "Mean Temperature Gradient",
            "Max Temperature Gradient",
            "Thermal Gradient Severity Index (Max/Mean)",
            "Gradient 90th/10th Percentile Ratio"
        ],
        "temperature_metrics": [
            "Maximum Temperature (°C)",
            "Average Temperature (°C)",
            "Hotspot Intensity Factor ((Tmax-Tavg)/Tavg)"
        ],
        "stress_metrics": [
            "Maximum Stress (Pa)",
            "Average Stress (Pa)",
            "Stress Coefficient of Variation"
        ],
        "correlation_metrics": [
            "Gradient-Stress Correlation Coefficient (r)",
            "Gradient-Stress Spearman Correlation",
            "Local Thermal-Mechanical Coupling Factor - Mean",
            "Local Thermal-Mechanical Coupling Factor - CV"
        ]
    }
    
    # Generate charts for each group
    for group_name, metrics_list in metric_groups.items():
        # Create normalized bar chart for this group
        fig = create_normalized_bar_chart(valid_names, valid_metrics, metrics_list, 
                                        f"{output_prefix}_{group_name}.png")
        plt.close(fig)

def create_gradient_histogram_comparison(valid_names, valid_arrays, output_file="gradient_histograms.png"):
    """
    Create improved histograms showing gradient distribution for each approach.
    
    Parameters:
    -----------
    valid_names : list
        List of optimization approach names
    valid_arrays : list
        List of arrays dictionaries
    output_file : str
        Output file name
    """
    plt.figure(figsize=(15, 6))
    
    # Set a consistent color palette
    colors = plt.cm.tab10(range(len(valid_names)))
    
    # Determine common x-axis limits for consistent comparison
    all_grads = []
    for arrays in valid_arrays:
        grad_data = arrays["Temperature Gradient"].flatten()
        grad_data = grad_data[~np.isnan(grad_data)]
        all_grads.extend(grad_data)
    
    if all_grads:
        # Remove outliers for better visualization (5th to 95th percentile)
        p05 = np.percentile(all_grads, 5)
        p95 = np.percentile(all_grads, 95)
        x_min, x_max = p05, p95
    else:
        x_min, x_max = 0, 1  # Default if no data
    
    for i, (name, arrays) in enumerate(zip(valid_names, valid_arrays)):
        plt.subplot(1, len(valid_names), i+1)
        
        grad_data = arrays["Temperature Gradient"].flatten()
        # Remove NaN values
        grad_data = grad_data[~np.isnan(grad_data)]
        
        if len(grad_data) > 0:
            # Calculate key statistics
            mean_val = np.mean(grad_data)
            std_val = np.std(grad_data)
            cv = std_val / mean_val if mean_val != 0 else float('nan')
            
            # Create histogram with KDE
            sns.histplot(grad_data, bins=50, kde=True, color=colors[i])
            
            # Add vertical line at mean
            plt.axvline(mean_val, color='red', linestyle='--', alpha=0.7, label=f'Mean: {mean_val:.1f}')
            
            # Add statistics annotation
            plt.annotate(f"Mean: {mean_val:.1f}\nStd Dev: {std_val:.1f}\nCV: {cv:.3f}", 
                        xy=(0.03, 0.97), xycoords='axes fraction',
                        ha='left', va='top', 
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            
            # Set consistent x-axis limits
            plt.xlim(x_min, x_max)
        else:
            plt.text(0.5, 0.5, "No data", ha='center', va='center', transform=plt.gca().transAxes)
        
        plt.title(f"{name}")
        plt.xlabel("Temperature Gradient Magnitude (°C/m)")
        if i == 0:
            plt.ylabel("Frequency")
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Gradient histograms saved to {output_file}")

def create_gradient_vector_comparison(valid_names, valid_arrays, output_file="gradient_vectors.png"):
    """
    Create enhanced temperature gradient vector visualization with improved legends.
    
    Parameters:
    -----------
    valid_names : list
        List of optimization approach names
    valid_arrays : list
        List of arrays dictionaries
    output_file : str
        Output file name
    """
    fig, axes = plt.subplots(1, len(valid_names), figsize=(6*len(valid_names), 5))
    
    # Handle the case of a single plot
    if len(valid_names) == 1:
        axes = [axes]
    
    # Create custom colormap for temperature
    temp_cmap = plt.cm.inferno
    
    for i, (name, arrays) in enumerate(zip(valid_names, valid_arrays)):
        ax = axes[i]
        
        # Get temperature gradient components
        xi = arrays["xi"]
        yi = arrays["yi"]
        Ti = arrays["Temperature Field"]
        grad_T = arrays["Temperature Gradient"]
        dT_dx = arrays["dT_dx"]
        dT_dy = arrays["dT_dy"]
        
        # Calculate statistics for annotation
        max_grad = np.nanmax(grad_T)
        mean_grad = np.nanmean(grad_T)
        std_grad = np.nanstd(grad_T)
        
        # Create temperature contour plot
        contour = ax.contourf(xi, yi, Ti, levels=20, cmap=temp_cmap, alpha=0.7)
        
        # Add temperature colorbar
        cbar_temp = plt.colorbar(contour, ax=ax)
        cbar_temp.set_label('Temperature (°C)')
        
        # Downsample for clearer visualization
        step = 10  # Adjust as needed based on grid size
        
        # Normalize vectors for better visualization
        magnitude = np.sqrt(dT_dx**2 + dT_dy**2)
        max_mag = np.nanmax(magnitude)
        
        if max_mag > 0:  # Avoid division by zero
            # Normalize to get direction with fixed length
            norm_dx = dT_dx / (magnitude + 1e-10) 
            norm_dy = dT_dy / (magnitude + 1e-10)
            
            # Scale vector length by gradient magnitude but cap for visibility
            scale_factor = 0.2  # Adjust as needed
            vis_dx = norm_dx * np.minimum(magnitude/max_mag, 1) * scale_factor
            vis_dy = norm_dy * np.minimum(magnitude/max_mag, 1) * scale_factor
            
            # Plot gradient vectors
            quiver = ax.quiver(xi[::step, ::step], yi[::step, ::step], 
                        vis_dx[::step, ::step], vis_dy[::step, ::step],
                        magnitude[::step, ::step], cmap='viridis',
                        scale=20, width=0.003, alpha=0.8)
            
            # Add colorbar for gradient magnitude
            cbar_grad = plt.colorbar(quiver, ax=ax)
            cbar_grad.set_label('Gradient Magnitude (°C/m)')
        
        # Add informative title and statistics
        ax.set_title(f"{name}\nTemp. Gradient Analysis", fontsize=11)
        
        # Add gradient statistics annotation
        stats_text = (f"Max Gradient: {max_grad:.1f} °C/m\n"
                    f"Mean Gradient: {mean_grad:.1f} °C/m\n"
                    f"Std Dev: {std_grad:.1f}")
        ax.text(0.03, 0.97, stats_text, transform=ax.transAxes,
                verticalalignment='top', horizontalalignment='left',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        ax.set_xlabel("X (m)")
        if i == 0:
            ax.set_ylabel("Y (m)")
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Enhanced gradient vector visualization saved to {output_file}")

def create_stress_temperature_comparison(valid_names, valid_arrays, output_file="temp_stress_comparison.png"):
    """
    Create a comprehensive visual comparison of temperature, gradient, and stress fields.
    
    Parameters:
    -----------
    valid_names : list
        List of optimization approach names
    valid_arrays : list
        List of arrays dictionaries
    output_file : str
        Output file name
    """
    # Define the fields to display
    fields = ["Temperature Field", "Temperature Gradient", "Stress Field"]
    field_cmaps = {
        "Temperature Field": "inferno",
        "Temperature Gradient": "viridis",
        "Stress Field": "coolwarm"
    }
    field_labels = {
        "Temperature Field": "Temperature (°C)",
        "Temperature Gradient": "Gradient (°C/m)",
        "Stress Field": "von Mises Stress (Pa)"
    }
    
    # Create figure with rows for fields and columns for approaches
    fig, axes = plt.subplots(len(fields), len(valid_names), 
                            figsize=(5*len(valid_names), 4*len(fields)))
    
    # Determine common color scale limits for each field
    common_limits = {}
    for field in fields:
        values = []
        for arrays in valid_arrays:
            if field in arrays and np.any(~np.isnan(arrays[field])):
                values.append(np.nanmin(arrays[field]))
                values.append(np.nanmax(arrays[field]))
        if values:
            common_limits[field] = (min(values), max(values))
    
    # Plot each field for each approach
    for row, field in enumerate(fields):
        for col, (name, arrays) in enumerate(zip(valid_names, valid_arrays)):
            # Get the right axis based on dimensions
            if len(fields) == 1 and len(valid_names) == 1:
                ax = axes
            elif len(fields) == 1:
                ax = axes[col]
            elif len(valid_names) == 1:
                ax = axes[row]
            else:
                ax = axes[row, col]
            
            # Get data for this field and approach
            data = arrays[field]
            xi = arrays["xi"]
            yi = arrays["yi"]
            
            # Use common limits for this field
            if field in common_limits:
                vmin, vmax = common_limits[field]
            else:
                vmin, vmax = np.nanmin(data), np.nanmax(data)
            
            # Create contour plot
            im = ax.contourf(xi, yi, data, levels=50, cmap=field_cmaps[field],
                            vmin=vmin, vmax=vmax)
            
            # Add colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label(field_labels[field])
            
            # Add title and labels
            if row == 0:
                ax.set_title(name)
            if col == 0:
                ax.set_ylabel(field.replace(" Field", ""))
            ax.set_xlabel("X (m)")
            
            # Calculate and display key statistics
            mean_val = np.nanmean(data)
            max_val = np.nanmax(data)
            if field == "Temperature Gradient":
                std_val = np.nanstd(data)
                cv = std_val / mean_val if mean_val != 0 else float('nan')
                stats_text = f"Mean: {mean_val:.1f}\nMax: {max_val:.1f}\nCV: {cv:.2f}"
            elif field == "Stress Field":
                std_val = np.nanstd(data)
                cv = std_val / mean_val if mean_val != 0 else float('nan')
                stats_text = f"Mean: {mean_val:.1e}\nMax: {max_val:.1e}\nCV: {cv:.2f}"
            else:
                stats_text = f"Mean: {mean_val:.1f}\nMax: {max_val:.1f}"
            
            # Add statistics annotation
            ax.text(0.03, 0.97, stats_text, transform=ax.transAxes,
                    verticalalignment='top', horizontalalignment='left',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Comprehensive field comparison saved to {output_file}")

def create_gradient_stress_correlation(valid_names, valid_arrays, valid_metrics, output_file="gradient_stress_correlation.png"):
    """
    Create scatter plots showing correlation between temperature gradient and stress.
    
    Parameters:
    -----------
    valid_names : list
        List of optimization approach names
    valid_arrays : list
        List of arrays dictionaries
    valid_metrics : list
        List of metrics dictionaries
    output_file : str
        Output file name
    """
    plt.figure(figsize=(5*len(valid_names), 5))
    
    # Set a consistent color palette
    colors = plt.cm.tab10(range(len(valid_names)))
    
    for i, (name, arrays, metrics) in enumerate(zip(valid_names, valid_arrays, valid_metrics)):
        plt.subplot(1, len(valid_names), i+1)
        
        # Extract flat arrays
        grad_T_flat = arrays["Temperature Gradient"].flatten()
        stress_flat = arrays["Stress Field"].flatten()
        
        # Remove NaN values
        mask = ~np.isnan(grad_T_flat) & ~np.isnan(stress_flat)
        grad_T_clean = grad_T_flat[mask]
        stress_clean = stress_flat[mask]
        
        if len(grad_T_clean) > 0:
            # Create hexbin plot for better visualization with large datasets
            hb = plt.hexbin(grad_T_clean, stress_clean, gridsize=50, cmap='viridis', 
                        mincnt=1, bins='log')
            
            # Add correlation coefficient to the plot
            corr = metrics.get("Gradient-Stress Correlation Coefficient (r)", np.nan)
            spearman = metrics.get("Gradient-Stress Spearman Correlation", np.nan)
            
            plt.text(0.05, 0.95, f"Pearson Correlation: {corr:.3f}\nSpearman Correlation: {spearman:.3f}", 
                    transform=plt.gca().transAxes,
                    fontsize=10, verticalalignment='top', 
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            
            # Add best fit line
            z = np.polyfit(grad_T_clean, stress_clean, 1)
            p = np.poly1d(z)
            x_min, x_max = np.min(grad_T_clean), np.max(grad_T_clean)
            plt.plot([x_min, x_max], [p(x_min), p(x_max)], "r--", lw=2)
            
            plt.colorbar(hb, label='log10(count)')
        else:
            plt.text(0.5, 0.5, "No data", ha='center', va='center', transform=plt.gca().transAxes)
        
        plt.title(f"{name}")
        plt.xlabel("Temperature Gradient (°C/m)")
        if i == 0:
            plt.ylabel("von Mises Stress (Pa)")
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Gradient-stress correlation plot saved to {output_file}")

def create_metrics_table(valid_names, valid_metrics, output_file="metrics_table.csv"):
    """
    Create a comprehensive metrics table with percentage comparisons.
    
    Parameters:
    -----------
    valid_names : list
        List of optimization approach names
    valid_metrics : list
        List of metrics dictionaries
    output_file : str
        Output file name
    """
    # Create DataFrame from metrics
    df_metrics = pd.DataFrame(index=list(valid_metrics[0].keys()))
    
    # Add raw values for each approach
    for i, name in enumerate(valid_names):
        df_metrics[name] = pd.Series(valid_metrics[i])
    
    # If we have at least two approaches, calculate percentage differences
    if len(valid_names) >= 2:
        # Use first approach as baseline
        baseline = valid_names[0]
        
        for name in valid_names[1:]:
            diff_col = f"{name} vs {baseline} (%)"
            df_metrics[diff_col] = 0.0
            
            for metric in df_metrics.index:
                baseline_val = df_metrics.loc[metric, baseline]
                current_val = df_metrics.loc[metric, name]
                
                # Skip if values are NaN or baseline is zero
                if pd.isna(baseline_val) or pd.isna(current_val) or baseline_val == 0:
                    df_metrics.loc[metric, diff_col] = np.nan
                else:
                    # Calculate percentage difference
                    pct_diff = ((current_val - baseline_val) / baseline_val) * 100
                    df_metrics.loc[metric, diff_col] = pct_diff
    
    # Save to CSV
    df_metrics.to_csv(output_file)
    print(f"Comprehensive metrics table saved to {output_file}")
    
    # Generate enhanced HTML version with improved formatting
    try:
        # Create a basic HTML table with conditional formatting using direct HTML/CSS
        html_output = "<html><head><style>\n"
        html_output += "table { border-collapse: collapse; width: 100%; }\n"
        html_output += "th, td { text-align: right; padding: 8px; border: 1px solid #ddd; }\n"
        html_output += "th { background-color: #4285f4; color: white; }\n"
        html_output += "tr:nth-child(even) { background-color: #f2f2f2; }\n"
        html_output += ".better { color: green; font-weight: bold; }\n"
        html_output += ".worse { color: red; font-weight: bold; }\n"
        html_output += ".metric-name { text-align: left; font-weight: bold; }\n"
        html_output += "</style></head><body>\n"
        
        # Create table header
        html_output += "<table>\n<tr><th>Metric</th>\n"
        for name in df_metrics.columns:
            html_output += f"<th>{name}</th>\n"
        html_output += "</tr>\n"
        
        # Create table rows with conditional formatting
        lower_is_better_keywords = ['Deviation', 'Severity', 'Coefficient', 'Correlation', 'Max', 'Intensity']
        
        for metric in df_metrics.index:
            html_output += "<tr>\n"
            html_output += f'<td class="metric-name">{metric}</td>\n'
            
            # Determine if lower values are better for this metric
            lower_is_better = any(kw in metric for kw in lower_is_better_keywords)
            
            for col in df_metrics.columns:
                val = df_metrics.loc[metric, col]
                
                if pd.isna(val):
                    html_output += "<td>-</td>\n"
                elif "vs" in col:  # Percentage difference column
                    # Format with color based on improvement
                    if (val < 0 and lower_is_better) or (val > 0 and not lower_is_better):
                        html_output += f'<td class="better">{val:.2f}%</td>\n'
                    else:
                        html_output += f'<td class="worse">{val:.2f}%</td>\n'
                elif isinstance(val, float):
                    if abs(val) < 0.01:
                        html_output += f"<td>{val:.2e}</td>\n"
                    else:
                        html_output += f"<td>{val:.4f}</td>\n"
                else:
                    html_output += f"<td>{val}</td>\n"
            
            html_output += "</tr>\n"
        
        html_output += "</table>\n</body></html>"
        
        with open(output_file.replace('.csv', '.html'), 'w', encoding='utf-8') as f:
            f.write(html_output)
        
        print(f"Enhanced HTML metrics table saved to {output_file.replace('.csv', '.html')}")
    except Exception as e:
        print(f"Warning: Could not create enhanced HTML output: {e}")
    
    return df_metrics

def create_summary_pdf(valid_names, valid_metrics, valid_arrays, output_file="thermal_mechanical_summary.pdf"):
    """
    Creates a single-page PDF summary of the thermal-mechanical gradient analysis results.
    """
    print(f"\nCreating summary PDF: {output_file}")
    
    # Create PDF
    with PdfPages(output_file) as pdf:
        # Create figure with custom layout - FIX: Adjust height_ratios to match our needs
        fig = plt.figure(figsize=(11, 8.5))  # US Letter size
        gs = GridSpec(4, 4, figure=fig, width_ratios=[1, 1, 1, 1.2], height_ratios=[0.2, 1, 1, 0.1])
        
        # Add title
        title_ax = fig.add_subplot(gs[0, :])
        title_ax.text(0.5, 0.5, "Thermal-Mechanical Gradient Analysis in 2.5D Chiplet Design", 
                    ha='center', va='center', fontsize=16, fontweight='bold')
        title_ax.axis('off')
        
        # Define plots to include
        fields = ["Temperature Field", "Temperature Gradient", "Stress Field"]
        field_cmaps = {
            "Temperature Field": "inferno",
            "Temperature Gradient": "viridis",
            "Stress Field": "coolwarm"
        }
        field_labels = {
            "Temperature Field": "Temperature (°C)",
            "Temperature Gradient": "Gradient (°C/m)",
            "Stress Field": "von Mises Stress (Pa)"
        }
        
        # Determine common color limits
        common_limits = {}
        for field in fields:
            values = []
            for arrays in valid_arrays:
                if field in arrays and np.any(~np.isnan(arrays[field])):
                    values.append(np.nanmin(arrays[field]))
                    values.append(np.nanmax(arrays[field]))
            if values:
                common_limits[field] = (min(values), max(values))
        
        # Create subplots for each field and approach
        for row, field in enumerate(fields):
            for col, (name, arrays) in enumerate(zip(valid_names, valid_arrays)):
                # FIX: Use row+1 but ensure it's within bounds
                ax = fig.add_subplot(gs[row+1, col])
                
                # Get data
                data = arrays[field]
                xi = arrays["xi"]
                yi = arrays["yi"]
                
                # Use common limits
                if field in common_limits:
                    vmin, vmax = common_limits[field]
                else:
                    vmin, vmax = np.nanmin(data), np.nanmax(data)
                
                # Create contour plot
                im = ax.contourf(xi, yi, data, levels=20, cmap=field_cmaps[field],
                               vmin=vmin, vmax=vmax)
                
                # Add colorbar
                cbar = plt.colorbar(im, ax=ax, pad=0.01, fraction=0.05)
                cbar.ax.tick_params(labelsize=7)
                
                # Add labels
                if row == 0:
                    ax.set_title(name, fontsize=9, pad=2)
                if col == 0:
                    ax.set_ylabel(field.replace(" Field", ""), fontsize=9)
                
                # Format axes
                ax.tick_params(axis='both', labelsize=7)
                ax.ticklabel_format(style='sci', scilimits=(-2, 3), axis='both')
                
                # Add compact stats in corner
                mean_val = np.nanmean(data)
                std_val = np.nanstd(data)
                cv = std_val / mean_val if mean_val != 0 else float('nan')
                
                if field == "Temperature Field":
                    stats_text = f"Mean: {mean_val:.1f}°C\nCV: {cv:.2f}"
                elif field == "Temperature Gradient":
                    stats_text = f"Mean: {mean_val:.0f}\nCV: {cv:.2f}"
                else:
                    stats_text = f"Mean: {mean_val:.1e}\nCV: {cv:.2f}"
                
                ax.text(0.03, 0.97, stats_text, transform=ax.transAxes,
                      fontsize=6, va='top', ha='left',
                      bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        # Add metrics table
        table_ax = fig.add_subplot(gs[1:3, 3])  # FIX: Explicitly set row range
        
        # [Rest of the function remains the same...] 
        
        # Select key metrics
        key_metrics = [
            "Standard Deviation (σ∇T)",
            "Mean Temperature Gradient",
            "Max Temperature Gradient",
            "Thermal Gradient Severity Index (Max/Mean)",
            "Hotspot Intensity Factor ((Tmax-Tavg)/Tavg)",
            "Gradient-Stress Correlation Coefficient (r)",
            "Stress Coefficient of Variation",
            "Maximum Temperature (°C)",
            "Average Temperature (°C)",
            "Maximum Stress (Pa)",
            "Average Stress (Pa)"
        ]
        
        # Format metric names for display
        display_names = [
            "Standard Deviation (σ∇T)",
            "Mean Temp. Gradient",
            "Max Temp. Gradient",
            "Thermal Gradient Severity Index",
            "Hotspot Intensity Factor",
            "Gradient-Stress Correlation",
            "Stress Coefficient of Variation",
            "Maximum Temperature (°C)",
            "Average Temperature (°C)",
            "Maximum Stress (Pa)",
            "Average Stress (Pa)"
        ]
        
        # Create data for table
        table_data = []
        for i, metric in enumerate(key_metrics):
            row_data = [display_names[i]]
            for j, metrics in enumerate(valid_metrics):
                val = metrics.get(metric, np.nan)
                if isinstance(val, float):
                    if abs(val) < 0.01 or abs(val) > 1000:
                        row_data.append(f"{val:.2e}")
                    else:
                        row_data.append(f"{val:.3f}")
                else:
                    row_data.append(str(val))
            table_data.append(row_data)
        
        # Calculate percentage difference if there are at least 2 approaches
        if len(valid_metrics) >= 2:
            row_data_with_pct = []
            for i, row in enumerate(table_data):
                metric = key_metrics[i]
                val1 = valid_metrics[0].get(metric, np.nan)
                val2 = valid_metrics[1].get(metric, np.nan)
                
                if not np.isnan(val1) and not np.isnan(val2) and val1 != 0:
                    pct_diff = ((val2 - val1) / val1) * 100
                    new_row = row + [f"{pct_diff:+.1f}%"]
                else:
                    new_row = row + ["N/A"]
                
                row_data_with_pct.append(new_row)
            
            table_data = row_data_with_pct
            col_headers = ["Metric"] + valid_names + ["% Diff"]
        else:
            col_headers = ["Metric"] + valid_names
        
        # Create and format table
        table = table_ax.table(
            cellText=table_data,
            colLabels=col_headers,
            loc='center',
            cellLoc='center'
        )
        
        # Style the table
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.5)
        
        # Color the header row
        for j, cell in enumerate(table._cells[(0, j)] for j in range(len(col_headers))):
            cell.set_facecolor('#4285F4')
            cell.set_text_props(color='white', fontweight='bold')
        
        # Color the metric names column
        for i, cell in enumerate(table._cells[(i, 0)] for i in range(1, len(table_data)+1)):
            cell.set_facecolor('#E8EAF6')
            cell.set_text_props(fontweight='bold')
        
        # Highlight percentage differences
        if len(valid_metrics) >= 2:
            for i, cell in enumerate(table._cells[(i+1, len(valid_names)+1)] for i in range(len(table_data))):
                text = cell.get_text().get_text()
                if text != "N/A":
                    try:
                        pct = float(text.strip('%+'))
                        if pct < 0:
                            cell.set_facecolor('#D5F5E3')  # Light green for improvements
                        elif pct > 0:
                            cell.set_facecolor('#FADBD8')  # Light red for regressions
                    except:
                        pass
        
        table_ax.axis('off')
        
        # Add a brief conclusion/analysis section at bottom
        if len(valid_metrics) >= 2:
            # Calculate key differences for analysis
            std_diff = ((valid_metrics[1].get("Standard Deviation (σ∇T)", 0) - 
                          valid_metrics[0].get("Standard Deviation (σ∇T)", 1)) / 
                         valid_metrics[0].get("Standard Deviation (σ∇T)", 1)) * 100
            
            severity_diff = ((valid_metrics[1].get("Thermal Gradient Severity Index (Max/Mean)", 0) - 
                               valid_metrics[0].get("Thermal Gradient Severity Index (Max/Mean)", 1)) / 
                              valid_metrics[0].get("Thermal Gradient Severity Index (Max/Mean)", 1)) * 100
            
            # Format analysis text based on calculations
            if std_diff < 0:
                gradient_text = f"• {valid_names[1]} shows improved gradient uniformity with {abs(std_diff):.1f}% lower standard deviation"
            else:
                gradient_text = f"• {valid_names[1]} shows {std_diff:.1f}% higher gradient standard deviation compared to {valid_names[0]}"
            
            analysis_text = (
                "Key Findings:\n"
                f"{gradient_text}\n"
                f"• Thermal Gradient Severity Index differs by {abs(severity_diff):.1f}% between approaches\n"
                "• Temperature distributions show distinct hotspot patterns between optimization strategies\n"
                "• Different gradient-stress correlation coefficients indicate varied thermal-mechanical coupling behavior"
            )
        else:
            analysis_text = "Analysis requires at least two optimization approaches for comparison."
        
        fig.text(0.5, 0.02, analysis_text, ha='center', va='bottom', fontsize=9, 
                 bbox=dict(boxstyle='round', facecolor='#F5F5F5', alpha=1.0))
        
        # Add footer with author info
        fig.text(0.98, 0.01, "Generated with Thermal-Mechanical Gradient Analysis Tool", 
                 ha='right', va='bottom', fontsize=6, style='italic')
        
        # Save the figure to PDF
        plt.tight_layout(rect=[0, 0.04, 1, 0.96])
        pdf.savefig(fig)
        plt.close()
    
    print(f"Summary PDF saved to {output_file}")
    return output_file

def create_combined_comparison(all_cost_functions):
    """
    Create comprehensive comparisons across all cost functions.
    
    Parameters:
    -----------
    all_cost_functions : dict
        Dictionary with cost function names as keys and tuples of (metrics, arrays) as values
    """
    # Extract names and data
    names = list(all_cost_functions.keys())
    metrics_list = [all_cost_functions[name][0] for name in names]
    arrays_list = [all_cost_functions[name][1] for name in names]
    
    # Filter to valid data only
    valid_data = []
    for i, (name, (metrics, arrays)) in enumerate(all_cost_functions.items()):
        if metrics and arrays:  # Check if dictionaries are not empty
            valid_data.append((name, metrics, arrays))
    
    if not valid_data:
        print("ERROR: No valid data available for any cost function")
        return
    
    # Extract valid names, metrics, and arrays
    valid_names = [name for name, _, _ in valid_data]
    valid_metrics = [metrics for _, metrics, _ in valid_data]
    valid_arrays = [arrays for _, _, arrays in valid_data]
    
    print(f"\nCreating comparisons for {len(valid_names)} valid datasets: {valid_names}")
    
    # Key metrics for the main comparison chart
    key_metrics = [
        "Standard Deviation (σ∇T)",
        "Thermal Gradient Severity Index (Max/Mean)",
        "Gradient-Stress Correlation Coefficient (r)",
        "Stress Coefficient of Variation"
    ]
    
    # 1. Create normalized bar chart for key metrics
    create_normalized_bar_chart(valid_names, valid_metrics, key_metrics)
    
    # 2. Create individual metric group comparisons
    create_individual_metric_comparisons(valid_names, valid_metrics)
    
    # 3. Create gradient histogram comparison
    create_gradient_histogram_comparison(valid_names, valid_arrays)
    
    # 4. Create enhanced gradient vector visualization
    create_gradient_vector_comparison(valid_names, valid_arrays)
    
    # 5. Create temperature-stress field comparison
    create_stress_temperature_comparison(valid_names, valid_arrays)
    
    # 6. Create gradient-stress correlation plots
    create_gradient_stress_correlation(valid_names, valid_arrays, valid_metrics)
    
    # 7. Create comprehensive metrics table with percentage comparisons
    metrics_df = create_metrics_table(valid_names, valid_metrics)
    
    # 8. Generate summary PDF for presentation
    create_summary_pdf(valid_names, valid_metrics, valid_arrays)
    
    print("\nAll comparisons complete!")

if __name__ == "__main__":
    try:
        print("\n=== THERMAL-MECHANICAL GRADIENT ANALYSIS ===")
        print("Starting file processing...")
        
        # First approach: Wirelength + Temperature
        # Process directly with known filenames
        print("Processing Wirelength + Temperature approach...")
        temp_file = "temp_multi_tw.txt"
        stress_file = "stress_multi_tw.txt"
        
        if os.path.exists(temp_file) and os.path.exists(stress_file):
            print(f"Using files: {temp_file}, {stress_file}")
            metrics_wire_temp, arrays_wire_temp = process_cost_function(
                temp_file, stress_file, "Wirelength + Temperature"
            )
        else:
            print(f"ERROR: Could not find required files for Wirelength + Temperature approach")
            print(f"Missing: {temp_file} or {stress_file}")
            metrics_wire_temp, arrays_wire_temp = {}, {}
        
        # Second approach: Wirelength + Stress
        # Process directly with known filenames
        print("\nProcessing Wirelength + Stress approach...")
        temp_file = "temp_multi_ws.txt"
        stress_file = "stress_multi_ws.txt"
        
        if os.path.exists(temp_file) and os.path.exists(stress_file):
            print(f"Using files: {temp_file}, {stress_file}")
            metrics_wire_stress, arrays_wire_stress = process_cost_function(
                temp_file, stress_file, "Wirelength + Stress"
            )
        else:
            print(f"ERROR: Could not find required files for Wirelength + Stress approach")
            print(f"Missing: {temp_file} or {stress_file}")
            metrics_wire_stress, arrays_wire_stress = {}, {}
        
        # Third approach: Wirelength + Stress + Temperature
        # Try different file patterns that are distinct from the first two approaches
        print("\nProcessing Wirelength + Stress + Temperature approach...")
        third_approach_patterns = [
            ("temp_multi_tws.txt", "stress_multi_tws.txt"),
            ("temp_ascend_stress_wire_thermal.txt", "stress_ascend_stress_wire_thermal.txt"),
            ("temp_wire_stress_thermal.txt", "stress_wire_stress_thermal.txt")
        ]
        
        found = False
        for temp_file, stress_file in third_approach_patterns:
            if os.path.exists(temp_file) and os.path.exists(stress_file):
                print(f"Found files for third approach: {temp_file}, {stress_file}")
                metrics_wire_stress_temp, arrays_wire_stress_temp = process_cost_function(
                    temp_file, stress_file, "Wirelength + Stress + Temperature"
                )
                found = True
                break
        
        if not found:
            print("WARNING: Could not find files for Wirelength + Stress + Temperature approach")
            print("Please ensure one of these file pairs exists:")
            for temp_file, stress_file in third_approach_patterns:
                print(f"  - {temp_file}, {stress_file}")
            
            # Create empty placeholder data to avoid errors
            metrics_wire_stress_temp, arrays_wire_stress_temp = {}, {}
            
            # Uncomment if you want to duplicate one of the existing approaches for testing
            # metrics_wire_stress_temp, arrays_wire_stress_temp = metrics_wire_temp, arrays_wire_temp
        
        # Combine all results for comparison
        all_cost_functions = {
            "Wirelength + Temperature": (metrics_wire_temp, arrays_wire_temp),
            "Wirelength + Stress": (metrics_wire_stress, arrays_wire_stress)
        }
        
        # Only add the third approach if data was found
        if found:
            all_cost_functions["Wirelength + Stress + Temperature"] = (metrics_wire_stress_temp, arrays_wire_stress_temp)
        
        # Create combined comparisons
        create_combined_comparison(all_cost_functions)
        
        print("\nAnalysis complete!")
        print("Output files saved in the current directory")
        print("Including thermal_mechanical_summary.pdf for presentation")
        
    except Exception as e:
        print(f"An error occurred during processing: {e}")
        import traceback
        traceback.print_exc()