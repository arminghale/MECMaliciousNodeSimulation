import os
import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
from pathlib import Path

EXPECTED_FILES = {
    "fault_summary": "table1_fault_summary.csv",
    "overall_summary": "table2_overall_summary.csv",
    "impact_severity": "table3_impact_severity.csv",
}


def parse_simulation_metadata(sim_name):
    """
    Expected format: {servers}_{faulty_pct}_{users_min}-{users_max}_{services_min}-{services_max}
    Example: 100_30_2-4_2-4
    """
    parts = sim_name.split("_")
    
    metadata = {
        "servers": None,
        "faulty_pct": None,
        "users_min": None,
        "users_max": None,
        "services_min": None,
        "services_max": None,
        "name": sim_name,
    }
    
    if len(parts) >= 2:
        try:
            metadata["servers"] = int(parts[0])
            metadata["faulty_pct"] = int(parts[1])
        except:
            pass
    
    if len(parts) >= 3:
        try:
            user_range = parts[2].split("-")
            if len(user_range) == 2:
                metadata["users_min"] = int(user_range[0])
                metadata["users_max"] = int(user_range[1])
        except:
            pass
    
    if len(parts) >= 4:
        try:
            service_range = parts[3].split("-")
            if len(service_range) == 2:
                metadata["services_min"] = int(service_range[0])
                metadata["services_max"] = int(service_range[1])
        except:
            pass
    
    return metadata


def discover_simulations(results_dir):
    simulations = {}
    results_path = Path(results_dir)
    
    if not results_path.exists():
        print(f"❌ Results directory not found: {results_dir}")
        return simulations
    
    # Scan for subdirectories containing Analysis folder
    for subdir in results_path.iterdir():
        if not subdir.is_dir():
            continue
        
        analysis_dir = subdir
        if not analysis_dir.exists():
            continue
        
        # Check if required files exist
        fault_summary_path = analysis_dir / EXPECTED_FILES["fault_summary"]
        overall_summary_path = analysis_dir / EXPECTED_FILES["overall_summary"]
        impact_severity_path = analysis_dir / EXPECTED_FILES["impact_severity"]
        
        if fault_summary_path.exists() and overall_summary_path.exists():
            metadata = parse_simulation_metadata(subdir.name)
            simulations[subdir.name] = {
                "path": str(subdir),
                "analysis_dir": str(analysis_dir),
                "fault_summary": str(fault_summary_path),
                "overall_summary": str(overall_summary_path),
                "impact_severity": str(impact_severity_path) if impact_severity_path.exists() else None,
                "metadata": metadata,
            }
            print(f"  ✓ Found simulation: {subdir.name} (Servers: {metadata['servers']}, Faulty: {metadata['faulty_pct']}%)")
    
    return simulations


def load_simulation_data(simulations):
    data = {}
    
    for sim_name, sim_info in simulations.items():
        try:
            fault_df = pd.read_csv(sim_info["fault_summary"])
            overall_df = pd.read_csv(sim_info["overall_summary"])
            
            impact_df = None
            if sim_info.get("impact_severity"):
                try:
                    impact_df = pd.read_csv(sim_info["impact_severity"])
                except:
                    pass
            
            data[sim_name] = {
                "fault_summary": fault_df,
                "overall_summary": overall_df,
                "impact_severity": impact_df,
                "path": sim_info["path"],
                "metadata": sim_info["metadata"],
            }
            print(f"  ✓ Loaded data: {sim_name}")
        except Exception as e:
            print(f"  ✗ Failed to load {sim_name}: {e}")
    
    return data


def create_comparison_charts(data, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    sim_names = list(data.keys())
    n_sims = len(sim_names)
    
    if n_sims == 0:
        print("❌ No simulation data to compare")
        return
    
    print(f"\n{'=' * 78}")
    print(f"  GENERATING COMPARISON CHARTS ({n_sims} simulations)")
    print(f"{'=' * 78}\n")
    
    # Extract simulation metadata for normalization
    sim_metadata = {}
    for sim_name in sim_names:
        metadata = data[sim_name]["metadata"]
        overall_df = data[sim_name]["overall_summary"]
        total_servers = metadata["servers"] if metadata["servers"] else len(overall_df)
        
        sim_metadata[sim_name] = {
            "servers": total_servers,
            "faulty_pct": metadata["faulty_pct"],
            "users_min": metadata["users_min"],
            "users_max": metadata["users_max"],
            "services_min": metadata["services_min"],
            "services_max": metadata["services_max"],
        }
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Request Processing Success Metrics Across Simulations", fontsize=16, fontweight="bold")
    
    # Extract metrics for each simulation
    metrics_data = {
        "Success Rate (%)": [],
        "Deadline Met Rate (%)": [],
        "Requests Processed": [],
        "Total Faults": [],
    }
    
    for sim_name in sim_names:
        overall_df = data[sim_name]["overall_summary"]
        
        # Aggregate across all server types
        if "Success Rate (%)" in overall_df.columns:
            avg_success = overall_df["Success Rate (%)"].mean()
            metrics_data["Success Rate (%)"].append(avg_success)
        else:
            metrics_data["Success Rate (%)"].append(0)
        
        if "Deadline Met Rate (%)" in overall_df.columns:
            avg_deadline = overall_df["Deadline Met Rate (%)"].mean()
            metrics_data["Deadline Met Rate (%)"].append(avg_deadline)
        else:
            metrics_data["Deadline Met Rate (%)"].append(0)
        
        if "Requests Proc" in overall_df.columns:
            total_proc = overall_df["Requests Proc"].sum()
            metrics_data["Requests Processed"].append(total_proc)
        else:
            metrics_data["Requests Processed"].append(0)
        
        # Calculate total faults from fault summary
        fault_df = data[sim_name]["fault_summary"]
        if all(col in fault_df.columns for col in ["Delayed", "Dropped", "Rejected", "False Reports"]):
            total_faults = (fault_df["Delayed"].sum() + fault_df["Dropped"].sum() + 
                          fault_df["Rejected"].sum() + fault_df["False Reports"].sum())
            metrics_data["Total Faults"].append(total_faults)
        else:
            metrics_data["Total Faults"].append(0)
    
    # Plot Success Rate
    ax = axes[0, 0]
    bars = ax.bar(range(n_sims), metrics_data["Success Rate (%)"], color='skyblue', alpha=0.8)
    ax.set_title("Average Success Rate", fontweight="bold")
    ax.set_xticks(range(n_sims))
    ax.set_xticklabels(sim_names, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Success Rate (%)")
    ax.set_ylim(0, 105)
    ax.grid(axis='y', alpha=0.3)
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
               ha='center', va='bottom', fontsize=9)
    
    # Plot Deadline Met Rate
    ax = axes[0, 1]
    bars = ax.bar(range(n_sims), metrics_data["Deadline Met Rate (%)"], color='lightgreen', alpha=0.8)
    ax.set_title("Average Deadline Met Rate", fontweight="bold")
    ax.set_xticks(range(n_sims))
    ax.set_xticklabels(sim_names, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Deadline Met Rate (%)")
    ax.set_ylim(0, 105)
    ax.grid(axis='y', alpha=0.3)
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
               ha='center', va='bottom', fontsize=9)
    
    # Plot Total Requests Processed
    ax = axes[1, 0]
    bars = ax.bar(range(n_sims), metrics_data["Requests Processed"], color='salmon', alpha=0.8)
    ax.set_title("Total Requests Processed", fontweight="bold")
    ax.set_xticks(range(n_sims))
    ax.set_xticklabels(sim_names, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Request Count")
    ax.grid(axis='y', alpha=0.3)
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height, f'{int(height)}',
               ha='center', va='bottom', fontsize=9)
    
    # Plot Total Faults Triggered
    ax = axes[1, 1]
    bars = ax.bar(range(n_sims), metrics_data["Total Faults"], color='coral', alpha=0.8)
    ax.set_title("Total Faults Triggered", fontweight="bold")
    ax.set_xticks(range(n_sims))
    ax.set_xticklabels(sim_names, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Fault Count")
    ax.grid(axis='y', alpha=0.3)
    for i, bar in enumerate(bars):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height, f'{int(height)}',
               ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    fig1_path = os.path.join(output_dir, "comparison_fig1_success_metrics.png")
    plt.savefig(fig1_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig1_path}")
    
    # ─────────────────────────────────────────────────────────────
    # Figure 2: Fault Type Distribution Comparison
    # ─────────────────────────────────────────────────────────────
    print("  Generating Figure 2: Fault Type Distribution...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Fault Type Distribution Across Simulations", fontsize=16, fontweight="bold")
    
    fault_types = ["Delayed", "Dropped", "Rejected", "False Reports"]
    
    for idx, fault_type in enumerate(fault_types):
        ax = axes[idx // 2, idx % 2]
        
        values = []
        for sim_name in sim_names:
            fault_df = data[sim_name]["fault_summary"]
            if fault_type in fault_df.columns:
                total = fault_df[fault_type].sum()
                values.append(total)
            else:
                values.append(0)
        
        bars = ax.bar(range(n_sims), values, color=plt.cm.Set3(idx), alpha=0.8)
        ax.set_title(f"{fault_type} Requests", fontweight="bold")
        ax.set_xticks(range(n_sims))
        ax.set_xticklabels(sim_names, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Count")
        ax.grid(axis='y', alpha=0.3)
        
        for i, bar in enumerate(bars):
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height, f'{int(height)}',
                       ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    fig2_path = os.path.join(output_dir, "comparison_fig2_fault_distribution.png")
    plt.savefig(fig2_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig2_path}")
    
    # ─────────────────────────────────────────────────────────────
    # Figure 3: Resource Utilization Comparison
    # ─────────────────────────────────────────────────────────────
    print("  Generating Figure 3: Resource Utilization Comparison...")
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("Resource Utilization Across Simulations", fontsize=16, fontweight="bold")
    
    resource_metrics = [
        ("Avg CPU (%)", "Average CPU Utilization"),
        ("Avg Memory (%)", "Average Memory Utilization"),
        ("Avg Power (W)", "Average Power Consumption"),
    ]
    
    for idx, (metric, title) in enumerate(resource_metrics):
        ax = axes[idx]
        
        values = []
        for sim_name in sim_names:
            overall_df = data[sim_name]["overall_summary"]
            if metric in overall_df.columns:
                avg_value = overall_df[metric].mean()
                values.append(avg_value)
            else:
                values.append(0)
        
        bars = ax.bar(range(n_sims), values, color='mediumpurple', alpha=0.8)
        ax.set_title(title, fontweight="bold")
        ax.set_xticks(range(n_sims))
        ax.set_xticklabels(sim_names, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel(metric.split("(")[1].strip(")") if "(" in metric else "Value")
        ax.grid(axis='y', alpha=0.3)
        
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}',
                   ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    fig3_path = os.path.join(output_dir, "comparison_fig3_resource_utilization.png")
    plt.savefig(fig3_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig3_path}")
    
    # ─────────────────────────────────────────────────────────────
    # Figure 4: Server Type Performance Heatmap
    # ─────────────────────────────────────────────────────────────
    print("  Generating Figure 4: Server Type Performance Heatmap...")
    
    # Collect all unique server types across simulations
    all_server_types = set()
    for sim_name in sim_names:
        overall_df = data[sim_name]["overall_summary"]
        if "Server Type" in overall_df.columns:
            all_server_types.update(overall_df["Server Type"].unique())
    
    server_types_sorted = sorted(all_server_types, key=lambda x: (x != "healthy", x))
    
    # Create heatmap data for key metrics
    heatmap_metrics = ["Success Rate (%)", "Deadline Met Rate (%)", "Requests Proc"]
    
    fig, axes = plt.subplots(1, len(heatmap_metrics), figsize=(18, 6))
    fig.suptitle("Server Type Performance Heatmap (Simulations × Server Types)", fontsize=16, fontweight="bold")
    
    for idx, metric in enumerate(heatmap_metrics):
        ax = axes[idx]
        
        # Build matrix: rows=simulations, cols=server_types
        matrix = np.zeros((n_sims, len(server_types_sorted)))
        
        for i, sim_name in enumerate(sim_names):
            overall_df = data[sim_name]["overall_summary"]
            for j, server_type in enumerate(server_types_sorted):
                if "Server Type" in overall_df.columns and metric in overall_df.columns:
                    row = overall_df[overall_df["Server Type"] == server_type]
                    if not row.empty:
                        matrix[i, j] = row[metric].values[0]
        
        # Plot heatmap
        im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', interpolation='nearest')
        ax.set_title(metric, fontweight="bold")
        ax.set_xticks(range(len(server_types_sorted)))
        ax.set_xticklabels(server_types_sorted, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(n_sims))
        ax.set_yticklabels(sim_names, fontsize=9)
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label(metric, rotation=270, labelpad=15)
        
        # Add text annotations
        for i in range(n_sims):
            for j in range(len(server_types_sorted)):
                value = matrix[i, j]
                text = ax.text(j, i, f'{value:.0f}',
                             ha="center", va="center", color="black", fontsize=7)
    
    plt.tight_layout()
    fig4_path = os.path.join(output_dir, "comparison_fig4_performance_heatmap.png")
    plt.savefig(fig4_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig4_path}")
    
    # ─────────────────────────────────────────────────────────────
    # Figure 5: Statistical Summary Table
    # ─────────────────────────────────────────────────────────────
    print("  Generating Figure 5: Statistical Summary...")
    
    summary_data = []
    for sim_name in sim_names:
        overall_df = data[sim_name]["overall_summary"]
        fault_df = data[sim_name]["fault_summary"]
        metadata = data[sim_name]["metadata"]
        
        # Format user and service ranges
        users_range = f"{metadata['users_min']}-{metadata['users_max']}" if metadata['users_min'] and metadata['users_max'] else "N/A"
        services_range = f"{metadata['services_min']}-{metadata['services_max']}" if metadata['services_min'] and metadata['services_max'] else "N/A"
        
        row = {
            "Simulation": sim_name,
            "Servers": metadata["servers"] if metadata["servers"] else len(overall_df),
            "Faulty %": metadata["faulty_pct"] if metadata["faulty_pct"] else "N/A",
            "Users": users_range,
            "Services": services_range,
            "Total Requests": overall_df["Requests Recv"].sum() if "Requests Recv" in overall_df.columns else 0,
            "Processed": overall_df["Requests Proc"].sum() if "Requests Proc" in overall_df.columns else 0,
            "Failed": overall_df["Requests Failed"].sum() if "Requests Failed" in overall_df.columns else 0,
            "Deadline Miss": overall_df["Deadline Missed"].sum() if "Deadline Missed" in overall_df.columns else 0,
            "Avg Success (%)": f"{overall_df['Success Rate (%)'].mean():.1f}" if "Success Rate (%)" in overall_df.columns else "0.0",
            "Avg Deadline Met (%)": f"{overall_df['Deadline Met Rate (%)'].mean():.1f}" if "Deadline Met Rate (%)" in overall_df.columns else "0.0",
            "Total Faults": (fault_df["Delayed"].sum() + fault_df["Dropped"].sum() + 
                           fault_df["Rejected"].sum() + fault_df["False Reports"].sum()) if all(col in fault_df.columns for col in ["Delayed", "Dropped", "Rejected", "False Reports"]) else 0,
        }
        summary_data.append(row)
    
    summary_df = pd.DataFrame(summary_data)
    
    # Save as CSV
    summary_csv_path = os.path.join(output_dir, "comparison_summary_table.csv")
    summary_df.to_csv(summary_csv_path, index=False)
    print(f"    ✓ Saved: {summary_csv_path}")
    
    # Create visual table
    fig, ax = plt.subplots(figsize=(14, max(4, n_sims * 0.5)))
    ax.axis('tight')
    ax.axis('off')
    
    table = ax.table(cellText=summary_df.values,
                    colLabels=summary_df.columns,
                    cellLoc='center',
                    loc='center',
                    bbox=[0, 0, 1, 1])
    
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)
    
    # Style header
    for i in range(len(summary_df.columns)):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(summary_df) + 1):
        for j in range(len(summary_df.columns)):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#f0f0f0')
    
    plt.title("Simulation Comparison Summary", fontsize=14, fontweight='bold', pad=20)
    
    fig5_path = os.path.join(output_dir, "comparison_fig5_summary_table.png")
    plt.savefig(fig5_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig5_path}")
    
    # Print summary to console
    print("\n" + "=" * 78)
    print("  COMPARISON SUMMARY")
    print("=" * 78)
    print(summary_df.to_string(index=False))
    print("=" * 78)


def create_parameter_trend_charts(data, output_dir):
    """Create charts showing how metrics vary with different parameters."""
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n{'=' * 78}")
    print(f"  GENERATING PARAMETER TREND ANALYSIS")
    print(f"{'=' * 78}\n")
    
    # Extract data for trend analysis
    trend_data = []
    for sim_name, sim_data in data.items():
        metadata = sim_data["metadata"]
        overall_df = sim_data["overall_summary"]
        fault_df = sim_data["fault_summary"]
        
        # Calculate aggregate metrics
        avg_success = overall_df["Success Rate (%)"].mean() if "Success Rate (%)" in overall_df.columns else 0
        avg_deadline = overall_df["Deadline Met Rate (%)"].mean() if "Deadline Met Rate (%)" in overall_df.columns else 0
        total_proc = overall_df["Requests Proc"].sum() if "Requests Proc" in overall_df.columns else 0
        total_failed = overall_df["Requests Failed"].sum() if "Requests Failed" in overall_df.columns else 0
        total_faults = (fault_df["Delayed"].sum() + fault_df["Dropped"].sum() + 
                       fault_df["Rejected"].sum() + fault_df["False Reports"].sum()) if all(col in fault_df.columns for col in ["Delayed", "Dropped", "Rejected", "False Reports"]) else 0
        
        trend_data.append({
            "name": sim_name,
            "servers": metadata["servers"],
            "faulty_pct": metadata["faulty_pct"],
            "users_min": metadata["users_min"],
            "users_max": metadata["users_max"],
            "services_min": metadata["services_min"],
            "services_max": metadata["services_max"],
            "avg_success": avg_success,
            "avg_deadline": avg_deadline,
            "total_proc": total_proc,
            "total_failed": total_failed,
            "total_faults": total_faults,
            "failure_rate": (total_failed / total_proc * 100) if total_proc > 0 else 0,
        })
    
    df = pd.DataFrame(trend_data)
    
    print("  Generating Figure A: Success Rate vs Server Count...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Performance Metrics vs Server Count", fontsize=16, fontweight="bold")
    
    # Group by server count
    if df["servers"].notna().any():
        server_groups = df.groupby("servers").agg({
            "avg_success": "mean",
            "avg_deadline": "mean",
            "total_proc": "sum",
            "total_faults": "sum",
        }).reset_index()
        
        # Success Rate
        ax = axes[0, 0]
        ax.plot(server_groups["servers"], server_groups["avg_success"], 
               marker='o', linewidth=2, markersize=8, color='green')
        ax.set_title("Success Rate vs Server Count", fontweight="bold")
        ax.set_xlabel("Number of Servers")
        ax.set_ylabel("Average Success Rate (%)")
        ax.grid(alpha=0.3)
        for i, row in server_groups.iterrows():
            ax.annotate(f'{row["avg_success"]:.1f}%', 
                       xy=(row["servers"], row["avg_success"]),
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        # Deadline Met Rate
        ax = axes[0, 1]
        ax.plot(server_groups["servers"], server_groups["avg_deadline"], 
               marker='s', linewidth=2, markersize=8, color='blue')
        ax.set_title("Deadline Met Rate vs Server Count", fontweight="bold")
        ax.set_xlabel("Number of Servers")
        ax.set_ylabel("Average Deadline Met Rate (%)")
        ax.grid(alpha=0.3)
        for i, row in server_groups.iterrows():
            ax.annotate(f'{row["avg_deadline"]:.1f}%', 
                       xy=(row["servers"], row["avg_deadline"]),
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        # Total Processed Requests
        ax = axes[1, 0]
        ax.bar(server_groups["servers"], server_groups["total_proc"], 
              color='skyblue', alpha=0.8)
        ax.set_title("Total Requests Processed vs Server Count", fontweight="bold")
        ax.set_xlabel("Number of Servers")
        ax.set_ylabel("Total Processed Requests")
        ax.grid(axis='y', alpha=0.3)
        for i, row in server_groups.iterrows():
            ax.text(row["servers"], row["total_proc"], f'{int(row["total_proc"])}',
                   ha='center', va='bottom', fontsize=9)
        
        # Total Faults
        ax = axes[1, 1]
        ax.bar(server_groups["servers"], server_groups["total_faults"], 
              color='coral', alpha=0.8)
        ax.set_title("Total Faults Triggered vs Server Count", fontweight="bold")
        ax.set_xlabel("Number of Servers")
        ax.set_ylabel("Total Faults")
        ax.grid(axis='y', alpha=0.3)
        for i, row in server_groups.iterrows():
            ax.text(row["servers"], row["total_faults"], f'{int(row["total_faults"])}',
                   ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    figA_path = os.path.join(output_dir, "param_figA_vs_server_count.png")
    plt.savefig(figA_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {figA_path}")
    
    print("  Generating Figure B: Performance vs Fault Percentage...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Performance Metrics vs Fault Percentage", fontsize=16, fontweight="bold")
    
    # Group by fault percentage
    if df["faulty_pct"].notna().any():
        fault_groups = df.groupby("faulty_pct").agg({
            "avg_success": "mean",
            "avg_deadline": "mean",
            "failure_rate": "mean",
            "total_faults": "sum",
        }).reset_index()
        
        # Success Rate
        ax = axes[0, 0]
        ax.plot(fault_groups["faulty_pct"], fault_groups["avg_success"], 
               marker='o', linewidth=2, markersize=8, color='green')
        ax.set_title("Success Rate vs Faulty Server %", fontweight="bold")
        ax.set_xlabel("Faulty Server Percentage (%)")
        ax.set_ylabel("Average Success Rate (%)")
        ax.grid(alpha=0.3)
        for i, row in fault_groups.iterrows():
            ax.annotate(f'{row["avg_success"]:.1f}%', 
                       xy=(row["faulty_pct"], row["avg_success"]),
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        # Deadline Met Rate
        ax = axes[0, 1]
        ax.plot(fault_groups["faulty_pct"], fault_groups["avg_deadline"], 
               marker='s', linewidth=2, markersize=8, color='blue')
        ax.set_title("Deadline Met Rate vs Faulty Server %", fontweight="bold")
        ax.set_xlabel("Faulty Server Percentage (%)")
        ax.set_ylabel("Average Deadline Met Rate (%)")
        ax.grid(alpha=0.3)
        for i, row in fault_groups.iterrows():
            ax.annotate(f'{row["avg_deadline"]:.1f}%', 
                       xy=(row["faulty_pct"], row["avg_deadline"]),
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        # Failure Rate
        ax = axes[1, 0]
        ax.plot(fault_groups["faulty_pct"], fault_groups["failure_rate"], 
               marker='^', linewidth=2, markersize=8, color='red')
        ax.set_title("Failure Rate vs Faulty Server %", fontweight="bold")
        ax.set_xlabel("Faulty Server Percentage (%)")
        ax.set_ylabel("Average Failure Rate (%)")
        ax.grid(alpha=0.3)
        for i, row in fault_groups.iterrows():
            ax.annotate(f'{row["failure_rate"]:.2f}%', 
                       xy=(row["faulty_pct"], row["failure_rate"]),
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        # Total Faults
        ax = axes[1, 1]
        ax.bar(fault_groups["faulty_pct"], fault_groups["total_faults"], 
              color='coral', alpha=0.8)
        ax.set_title("Total Faults vs Faulty Server %", fontweight="bold")
        ax.set_xlabel("Faulty Server Percentage (%)")
        ax.set_ylabel("Total Faults Triggered")
        ax.grid(axis='y', alpha=0.3)
        for i, row in fault_groups.iterrows():
            ax.text(row["faulty_pct"], row["total_faults"], f'{int(row["total_faults"])}',
                   ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    figB_path = os.path.join(output_dir, "param_figB_vs_fault_percentage.png")
    plt.savefig(figB_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {figB_path}")
    
    print("  Generating Figure C: 2D Parameter Heatmap...")
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Performance Heatmap: Server Count × Fault Percentage", fontsize=16, fontweight="bold")
    
    if df["servers"].notna().any() and df["faulty_pct"].notna().any():
        # Create pivot tables
        pivot_success = df.pivot_table(values="avg_success", 
                                       index="faulty_pct", 
                                       columns="servers", 
                                       aggfunc="mean")
        pivot_deadline = df.pivot_table(values="avg_deadline", 
                                        index="faulty_pct", 
                                        columns="servers", 
                                        aggfunc="mean")
        
        # Success Rate Heatmap
        ax = axes[0]
        im = ax.imshow(pivot_success.values, cmap='RdYlGn', aspect='auto', 
                      interpolation='nearest', vmin=0, vmax=100)
        ax.set_title("Success Rate (%)", fontweight="bold")
        ax.set_xticks(range(len(pivot_success.columns)))
        ax.set_xticklabels(pivot_success.columns, fontsize=9)
        ax.set_yticks(range(len(pivot_success.index)))
        ax.set_yticklabels(pivot_success.index, fontsize=9)
        ax.set_xlabel("Number of Servers")
        ax.set_ylabel("Faulty Server Percentage (%)")
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label("Success Rate (%)", rotation=270, labelpad=15)
        
        # Add text annotations
        for i in range(len(pivot_success.index)):
            for j in range(len(pivot_success.columns)):
                value = pivot_success.values[i, j]
                if not np.isnan(value):
                    ax.text(j, i, f'{value:.1f}', ha="center", va="center", 
                           color="black", fontsize=9)
        
        # Deadline Met Rate Heatmap
        ax = axes[1]
        im = ax.imshow(pivot_deadline.values, cmap='RdYlGn', aspect='auto', 
                      interpolation='nearest', vmin=0, vmax=100)
        ax.set_title("Deadline Met Rate (%)", fontweight="bold")
        ax.set_xticks(range(len(pivot_deadline.columns)))
        ax.set_xticklabels(pivot_deadline.columns, fontsize=9)
        ax.set_yticks(range(len(pivot_deadline.index)))
        ax.set_yticklabels(pivot_deadline.index, fontsize=9)
        ax.set_xlabel("Number of Servers")
        ax.set_ylabel("Faulty Server Percentage (%)")
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label("Deadline Met Rate (%)", rotation=270, labelpad=15)
        
        # Add text annotations
        for i in range(len(pivot_deadline.index)):
            for j in range(len(pivot_deadline.columns)):
                value = pivot_deadline.values[i, j]
                if not np.isnan(value):
                    ax.text(j, i, f'{value:.1f}', ha="center", va="center", 
                           color="black", fontsize=9)
    
    plt.tight_layout()
    figC_path = os.path.join(output_dir, "param_figC_heatmap_servers_faults.png")
    plt.savefig(figC_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {figC_path}")
    
    print("  Generating Parameter Correlation Analysis...")
    
    # Create correlation matrix
    corr_df = df[["servers", "faulty_pct", "avg_success", "avg_deadline", "failure_rate"]].copy()
    corr_df = corr_df.dropna()
    
    if len(corr_df) > 1:
        correlation_matrix = corr_df.corr()
        
        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(correlation_matrix, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
        
        # Labels
        labels = ["Server Count", "Fault %", "Success Rate", "Deadline Met", "Failure Rate"]
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=10)
        ax.set_yticklabels(labels, fontsize=10)
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label("Correlation Coefficient", rotation=270, labelpad=15)
        
        # Add correlation values
        for i in range(len(labels)):
            for j in range(len(labels)):
                value = correlation_matrix.iloc[i, j]
                ax.text(j, i, f'{value:.2f}', ha="center", va="center",
                       color="white" if abs(value) > 0.5 else "black", fontsize=11, fontweight="bold")
        
        plt.title("Parameter Correlation Matrix", fontsize=14, fontweight="bold", pad=15)
        plt.tight_layout()
        figD_path = os.path.join(output_dir, "param_figD_correlation_matrix.png")
        plt.savefig(figD_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Saved: {figD_path}")
    
    param_csv_path = os.path.join(output_dir, "parameter_trends.csv")
    df.to_csv(param_csv_path, index=False)
    print(f"    ✓ Saved: {param_csv_path}")
    
    print(f"\n{'=' * 78}")
    print(f"  PARAMETER TREND ANALYSIS COMPLETE")
    print(f"{'=' * 78}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Compare multiple EdgeSimPy simulation results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--results-dir",
        type=str,
        default="Analysis",
        help="Directory containing simulation result folders (default: results)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Compare_Analysis",
        help="Output directory for comparison charts (default: comparison_analysis)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 78)
    print("  SIMULATION COMPARISON TOOL")
    print("=" * 78)
    print(f"  Results directory: {args.results_dir}")
    print(f"  Output directory:  {args.output_dir}")
    print("=" * 78 + "\n")
    
    # Discover simulations
    print("Discovering simulations...")
    simulations = discover_simulations(args.results_dir)
    
    if not simulations:
        print("\n❌ No valid simulation results found.")
        print(f"   Make sure '{args.results_dir}' contains subdirectories with 'Analysis' folders")
        print(f"   containing {EXPECTED_FILES['fault_summary']} and {EXPECTED_FILES['overall_summary']}")
        return 1
    
    print(f"\n✓ Found {len(simulations)} simulation(s)\n")
    
    # Load data
    print("Loading simulation data...")
    data = load_simulation_data(simulations)
    
    if not data:
        print("\n❌ Failed to load any simulation data.")
        return 1
    
    print(f"\n✓ Loaded {len(data)} simulation(s)\n")
    
    # Generate comparisons
    create_comparison_charts(data, args.output_dir)
    
    # Generate parameter trend analysis
    create_parameter_trend_charts(data, args.output_dir)
    
    print(f"\n{'=' * 78}")
    print(f"  COMPARISON COMPLETE")
    print(f"  Results saved to: {args.output_dir}/")
    print(f"{'=' * 78}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
