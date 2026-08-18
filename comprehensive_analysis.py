import json
import statistics
import os
from typing import Dict, List, Any
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


class ComprehensiveAnalyzer:
    """
    Analyzes Byzantine fault simulation results across multiple scenarios
    with comprehensive metrics extraction and visualization.
    """
    
    def __init__(self, metrics_files: Dict[str, str]):
        """
        Initialize analyzer with metric files from all scenarios.
        
        Args:
            metrics_files: Dict mapping scenario names to JSON file paths
        """
        self.results = {}
        for scenario, filepath in metrics_files.items():
            try:
                with open(filepath, 'r') as f:
                    self.results[scenario] = json.load(f)
                    print(f"✓ Loaded {scenario}")
            except FileNotFoundError:
                print(f"✗ Missing {filepath}")
    
    def extract_server_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Extract comprehensive server-level metrics."""
        analysis = {}
        
        for scenario_name, metrics in self.results.items():
            edges = metrics.get('edge_servers', metrics.get('edges', []))
            
            if not edges:
                continue
            
            faulty = [e for e in edges if e.get('fault_type')]
            normal = [e for e in edges if not e.get('fault_type')]
            
            cpu_utils = [e.get('utilization_percent', 0) for e in edges]
            services_per_server = [e.get('services_hosted', 0) for e in edges]
            power_vals = [e.get('power_consumption', 0) for e in edges]
            
            analysis[scenario_name] = {
                'server_count': len(edges),
                'faulty_count': len(faulty),
                'normal_count': len(normal),
                'malicious_percentage': (len(faulty) / len(edges) * 100) if edges else 0,
                
                # CPU Utilization
                'cpu_util_avg': statistics.mean(cpu_utils) if cpu_utils else 0,
                'cpu_util_max': max(cpu_utils) if cpu_utils else 0,
                'cpu_util_min': min(cpu_utils) if cpu_utils else 0,
                'cpu_util_stdev': statistics.stdev(cpu_utils) if len(cpu_utils) > 1 else 0,
                
                # Service Hosting
                'avg_services_per_server': statistics.mean(services_per_server) if services_per_server else 0,
                'total_services_hosted': sum(services_per_server),
                'max_services_on_server': max(services_per_server) if services_per_server else 0,
                'service_distribution_fairness': calculate_gini(services_per_server),
                
                # Power Consumption
                'total_power_consumption': sum(power_vals),
                'avg_power_per_server': statistics.mean(power_vals) if power_vals else 0,
                'max_power_server': max(power_vals) if power_vals else 0,
                
                # Fault Impact
                'total_dropped_requests': sum(e.get('dropped_requests', 0) for e in faulty),
                'total_rejected_requests': sum(e.get('rejected_requests', 0) for e in faulty),
                'total_false_reports': sum(e.get('false_reports_count', 0) for e in faulty),
                'total_delayed_requests': sum(e.get('delayed_requests', 0) for e in faulty),
                'avg_faults_per_server': sum(e.get('total_faults_triggered', 0) for e in faulty) / len(faulty) if faulty else 0,
            }
        
        return analysis
    
    def extract_service_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Extract comprehensive service-level metrics."""
        analysis = {}
        
        for scenario_name, metrics in self.results.items():
            services = metrics.get('services', [])
            
            if not services:
                continue
            
            placed = [s for s in services if s.get('server')]
            unplaced = [s for s in services if not s.get('server')]
            
            processing_times = [s.get('processing_time', 0) for s in placed]
            requests_proc = [s.get('requests_processed', 0) for s in services]
            
            analysis[scenario_name] = {
                'total_services': len(services),
                'placed_services': len(placed),
                'unplaced_services': len(unplaced),
                'placement_ratio': (len(placed) / len(services) * 100) if services else 0,
                
                # Processing Metrics
                'avg_processing_time': statistics.mean(processing_times) if processing_times else 0,
                'max_processing_time': max(processing_times) if processing_times else 0,
                'total_requests_processed': sum(requests_proc),
                'avg_requests_per_service': statistics.mean(requests_proc) if requests_proc else 0,
                
                # Service Utilization
                'services_with_requests': len([s for s in services if s.get('requests_processed', 0) > 0]),
                'idle_services': len([s for s in services if s.get('requests_processed', 0) == 0]),
            }
        
        return analysis
    
    def extract_user_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Extract user-centric metrics."""
        analysis = {}
        
        for scenario_name, metrics in self.results.items():
            users = metrics.get('users', [])
            
            if not users:
                continue
            
            analysis[scenario_name] = {
                'total_users': len(users),
                'active_users': sum(1 for u in users if u.get('active', False)),
            }
        
        return analysis
    
    def calculate_impact_metrics(self) -> Dict[str, Dict[str, float]]:
        """Calculate Byzantine fault impact metrics."""
        impact = {}
        
        baseline_data = None
        baseline_name = next((name for name in self.results.keys() if 'baseline' in name.lower()), None)
        
        if baseline_name:
            baseline_data = self.extract_server_metrics()[baseline_name]
        
        for scenario_name, metrics in self.results.items():
            if 'baseline' in scenario_name.lower():
                continue
            
            edges = metrics.get('edge_servers', metrics.get('edges', []))
            if not edges or not baseline_data:
                continue
            
            current_data = self.extract_server_metrics().get(scenario_name)
            if not current_data:
                continue
            
            # Calculate degradation percentages
            cpu_degradation = ((current_data['cpu_util_avg'] - baseline_data['cpu_util_avg']) / 
                              max(0.1, baseline_data['cpu_util_avg']) * 100)
            
            service_reduction = ((baseline_data['total_services_hosted'] - current_data['total_services_hosted']) / 
                                max(1, baseline_data['total_services_hosted']) * 100)
            
            power_increase = ((current_data['total_power_consumption'] - baseline_data['total_power_consumption']) / 
                             max(1, baseline_data['total_power_consumption']) * 100)
            
            impact[scenario_name] = {
                'cpu_utilization_change_percent': cpu_degradation,
                'service_hosting_reduction_percent': service_reduction,
                'power_consumption_increase_percent': power_increase,
                'total_fault_events': (current_data['total_dropped_requests'] + 
                                      current_data['total_rejected_requests'] + 
                                      current_data['total_delayed_requests']),
                'avg_impact_per_faulty_server': ((current_data['total_dropped_requests'] + 
                                                 current_data['total_rejected_requests'] + 
                                                 current_data['total_delayed_requests']) / 
                                                max(1, current_data['faulty_count'])),
            }
        
        return impact
    
    def generate_comprehensive_report(self) -> str:
        """Generate detailed text report."""
        report = []
        report.append("=" * 100)
        report.append("COMPREHENSIVE BYZANTINE FAULT SIMULATION ANALYSIS REPORT".center(100))
        report.append("=" * 100)
        
        # 1. Server Analysis
        report.append("\n" + "SERVER-LEVEL ANALYSIS".center(100))
        report.append("-" * 100)
        server_metrics = self.extract_server_metrics()
        
        for scenario, metrics in sorted(server_metrics.items()):
            report.append(f"\n{scenario.upper()}")
            report.append(f"  Servers: {metrics['server_count']} (Faulty: {metrics['faulty_count']}, Normal: {metrics['normal_count']})")
            report.append(f"  Malicious Percentage: {metrics['malicious_percentage']:.1f}%")
            report.append(f"  CPU Utilization: {metrics['cpu_util_avg']:.1f}% (±{metrics['cpu_util_stdev']:.1f}%, min={metrics['cpu_util_min']:.1f}%, max={metrics['cpu_util_max']:.1f}%)")
            report.append(f"  Service Distribution: Avg {metrics['avg_services_per_server']:.1f}/server, Total {metrics['total_services_hosted']}, Fairness (Gini) {metrics['service_distribution_fairness']:.3f}")
            report.append(f"  Power Consumption: {metrics['total_power_consumption']:.0f}W total, {metrics['avg_power_per_server']:.1f}W avg/server")
            report.append(f"  Fault Metrics:")
            report.append(f"    - Dropped Requests: {metrics['total_dropped_requests']}")
            report.append(f"    - Rejected Requests: {metrics['total_rejected_requests']}")
            report.append(f"    - False Reports: {metrics['total_false_reports']}")
            report.append(f"    - Delayed Requests: {metrics['total_delayed_requests']}")
            report.append(f"    - Avg Faults/Faulty Server: {metrics['avg_faults_per_server']:.1f}")
        
        # 2. Service Analysis
        report.append("\n" + "SERVICE-LEVEL ANALYSIS".center(100))
        report.append("-" * 100)
        service_metrics = self.extract_service_metrics()
        
        for scenario, metrics in sorted(service_metrics.items()):
            report.append(f"\n{scenario.upper()}")
            report.append(f"  Service Placement: {metrics['placed_services']}/{metrics['total_services']} placed ({metrics['placement_ratio']:.1f}%)")
            report.append(f"  Unplaced Services: {metrics['unplaced_services']}")
            report.append(f"  Processing: Avg {metrics['avg_processing_time']:.1f}ms, Max {metrics['max_processing_time']:.1f}ms")
            report.append(f"  Throughput: {metrics['total_requests_processed']} total requests processed")
            report.append(f"  Active Services: {metrics['services_with_requests']} active, {metrics['idle_services']} idle")
        
        # 3. User Analysis
        report.append("\n" + "USER-LEVEL ANALYSIS".center(100))
        report.append("-" * 100)
        user_metrics = self.extract_user_metrics()
        
        for scenario, metrics in sorted(user_metrics.items()):
            report.append(f"\n{scenario.upper()}")
            report.append(f"  Users: {metrics['total_users']} total, {metrics['active_users']} active")
        
        # 4. Impact Analysis
        report.append("\n" + "BYZANTINE FAULT IMPACT ANALYSIS".center(100))
        report.append("-" * 100)
        impact_metrics = self.calculate_impact_metrics()
        
        for scenario, metrics in sorted(impact_metrics.items()):
            report.append(f"\n{scenario.upper()}")
            report.append(f"  CPU Utilization Change: {metrics['cpu_utilization_change_percent']:+.1f}%")
            report.append(f"  Service Hosting Reduction: {metrics['service_hosting_reduction_percent']:.1f}%")
            report.append(f"  Power Consumption Change: {metrics['power_consumption_increase_percent']:+.1f}%")
            report.append(f"  Total Fault Events: {metrics['total_fault_events']}")
            report.append(f"  Avg Impact per Faulty Server: {metrics['avg_impact_per_faulty_server']:.1f} faults")
        
        report.append("\n" + "=" * 100)
        report.append("END OF REPORT".center(100))
        report.append("=" * 100)
        
        return "\n".join(report)
    
    def create_visualizations(self, outdir: str = "ComprehensiveAnalysis"):
        """Create all visualization charts."""
        os.makedirs(outdir, exist_ok=True)
        
        server_metrics = self.extract_server_metrics()
        service_metrics = self.extract_service_metrics()
        impact_metrics = self.calculate_impact_metrics()
        scenarios = list(server_metrics.keys())
        
        if not scenarios:
            print("No data to visualize")
            return
        
        # 1. CPU Utilization Comparison
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            cpu_avg = [server_metrics[s]['cpu_util_avg'] for s in scenarios]
            cpu_stdev = [server_metrics[s]['cpu_util_stdev'] for s in scenarios]
            
            x = np.arange(len(scenarios))
            bars = ax.bar(x, cpu_avg, yerr=cpu_stdev, capsize=5, alpha=0.7, color='steelblue')
            ax.set_ylabel('CPU Utilization (%)', fontsize=11)
            ax.set_title('Average CPU Utilization by Scenario (with Std Dev)', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.set_ylim([0, 100])
            
            # Add value labels on bars
            for i, (bar, val) in enumerate(zip(bars, cpu_avg)):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                       f'{val:.1f}%', ha='center', va='bottom', fontsize=9)
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '01_cpu_utilization.png'), dpi=300)
            plt.close()
            print(f"✓ Created 01_cpu_utilization.png")
        except Exception as e:
            print(f"✗ Failed to create CPU utilization chart: {e}")
        
        # 2. Service Placement Success Rate
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            placement_ratios = [service_metrics[s]['placement_ratio'] for s in scenarios]
            
            x = np.arange(len(scenarios))
            bars = ax.bar(x, placement_ratios, alpha=0.7, color='green')
            ax.axhline(y=100, color='r', linestyle='--', label='Target (100%)', linewidth=2)
            ax.set_ylabel('Placement Rate (%)', fontsize=11)
            ax.set_title('Service Placement Success Rate by Scenario', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.set_ylim([0, 105])
            ax.legend()
            
            for bar, val in zip(bars, placement_ratios):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                       f'{val:.1f}%', ha='center', va='bottom', fontsize=9)
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '02_service_placement_ratio.png'), dpi=300)
            plt.close()
            print(f"✓ Created 02_service_placement_ratio.png")
        except Exception as e:
            print(f"✗ Failed to create service placement chart: {e}")
        
        # 3. Power Consumption
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            power_total = [server_metrics[s]['total_power_consumption'] for s in scenarios]
            power_avg = [server_metrics[s]['avg_power_per_server'] for s in scenarios]
            
            x = np.arange(len(scenarios))
            width = 0.35
            
            ax.bar(x - width/2, power_total, width, label='Total', alpha=0.7, color='red')
            ax2 = ax.twinx()
            ax2.plot(x, power_avg, marker='o', color='darkred', linewidth=2, markersize=8, label='Avg/Server')
            
            ax.set_ylabel('Total Power (W)', fontsize=11, color='red')
            ax2.set_ylabel('Avg Power per Server (W)', fontsize=11, color='darkred')
            ax.set_title('Power Consumption Analysis', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.tick_params(axis='y', labelcolor='red')
            ax2.tick_params(axis='y', labelcolor='darkred')
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '03_power_consumption.png'), dpi=300)
            plt.close()
            print(f"✓ Created 03_power_consumption.png")
        except Exception as e:
            print(f"✗ Failed to create power consumption chart: {e}")
        
        # 4. Fault Event Breakdown
        try:
            fig, ax = plt.subplots(figsize=(14, 6))
            
            dropped = [server_metrics[s]['total_dropped_requests'] for s in scenarios]
            rejected = [server_metrics[s]['total_rejected_requests'] for s in scenarios]
            delayed = [server_metrics[s]['total_delayed_requests'] for s in scenarios]
            false_reports = [server_metrics[s]['total_false_reports'] for s in scenarios]
            
            x = np.arange(len(scenarios))
            width = 0.2
            
            ax.bar(x - 1.5*width, dropped, width, label='Dropped', alpha=0.8)
            ax.bar(x - 0.5*width, rejected, width, label='Rejected', alpha=0.8)
            ax.bar(x + 0.5*width, delayed, width, label='Delayed', alpha=0.8)
            ax.bar(x + 1.5*width, false_reports, width, label='False Reports', alpha=0.8)
            
            ax.set_ylabel('Event Count', fontsize=11)
            ax.set_title('Byzantine Fault Events by Type and Scenario', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.legend(loc='upper left')
            ax.grid(axis='y', alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '04_fault_events_breakdown.png'), dpi=300)
            plt.close()
            print(f"✓ Created 04_fault_events_breakdown.png")
        except Exception as e:
            print(f"✗ Failed to create fault events chart: {e}")
        
        # 5. Service Distribution Fairness (Gini Coefficient)
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            fairness = [server_metrics[s]['service_distribution_fairness'] for s in scenarios]
            
            colors = ['green' if g < 0.3 else 'orange' if g < 0.6 else 'red' for g in fairness]
            
            x = np.arange(len(scenarios))
            bars = ax.bar(x, fairness, alpha=0.7, color=colors)
            
            ax.axhline(y=0.3, color='green', linestyle='--', alpha=0.5, label='Fair (< 0.3)')
            ax.axhline(y=0.6, color='red', linestyle='--', alpha=0.5, label='Unfair (> 0.6)')
            
            ax.set_ylabel('Gini Coefficient', fontsize=11)
            ax.set_title('Service Distribution Fairness (Lower is Better)', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.set_ylim([0, 1])
            ax.legend()
            
            for bar, val in zip(bars, fairness):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, 
                       f'{val:.3f}', ha='center', va='bottom', fontsize=9)
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '05_fairness_gini.png'), dpi=300)
            plt.close()
            print(f"✓ Created 05_fairness_gini.png")
        except Exception as e:
            print(f"✗ Failed to create fairness chart: {e}")
        
        # 6. Impact Metrics (Degradation %)
        try:
            fig, axes = plt.subplots(1, 3, figsize=(16, 5))
            impact_scenarios = list(impact_metrics.keys())
            
            if impact_scenarios:
                cpu_change = [impact_metrics[s]['cpu_utilization_change_percent'] for s in impact_scenarios]
                service_red = [impact_metrics[s]['service_hosting_reduction_percent'] for s in impact_scenarios]
                power_change = [impact_metrics[s]['power_consumption_increase_percent'] for s in impact_scenarios]
                
                x = np.arange(len(impact_scenarios))
                
                # CPU Change
                colors_cpu = ['red' if v > 0 else 'green' for v in cpu_change]
                axes[0].bar(x, cpu_change, color=colors_cpu, alpha=0.7)
                axes[0].axhline(y=0, color='black', linestyle='-', linewidth=0.8)
                axes[0].set_ylabel('Change (%)', fontsize=10)
                axes[0].set_title('CPU Util. Change vs Baseline', fontsize=11, fontweight='bold')
                axes[0].set_xticks(x)
                axes[0].set_xticklabels(impact_scenarios, rotation=45, ha='right')
                axes[0].grid(axis='y', alpha=0.3)
                
                # Service Reduction
                axes[1].bar(x, service_red, color='orange', alpha=0.7)
                axes[1].set_ylabel('Reduction (%)', fontsize=10)
                axes[1].set_title('Service Hosting Reduction', fontsize=11, fontweight='bold')
                axes[1].set_xticks(x)
                axes[1].set_xticklabels(impact_scenarios, rotation=45, ha='right')
                axes[1].grid(axis='y', alpha=0.3)
                
                # Power Change
                colors_power = ['red' if v > 0 else 'green' for v in power_change]
                axes[2].bar(x, power_change, color=colors_power, alpha=0.7)
                axes[2].axhline(y=0, color='black', linestyle='-', linewidth=0.8)
                axes[2].set_ylabel('Change (%)', fontsize=10)
                axes[2].set_title('Power Consumption Change', fontsize=11, fontweight='bold')
                axes[2].set_xticks(x)
                axes[2].set_xticklabels(impact_scenarios, rotation=45, ha='right')
                axes[2].grid(axis='y', alpha=0.3)
                
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, '06_impact_degradation.png'), dpi=300)
                plt.close()
                print(f"✓ Created 06_impact_degradation.png")
        except Exception as e:
            print(f"✗ Failed to create impact metrics chart: {e}")
        
        # 7. Malicious Server Count and Impact
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            faulty_counts = [server_metrics[s]['faulty_count'] for s in scenarios]
            fault_events = [impact_metrics.get(s, {}).get('total_fault_events', 0) for s in scenarios if s in impact_metrics]
            impact_scenarios_list = list(impact_metrics.keys())
            
            x = np.arange(len(scenarios))
            
            ax.bar(x, faulty_counts, alpha=0.7, color='red', label='Faulty Servers')
            ax.set_ylabel('Number of Servers', fontsize=11)
            ax.set_xlabel('Scenario', fontsize=11)
            ax.set_title('Faulty Server Distribution', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.legend()
            
            for i, (bar, val) in enumerate(zip(ax.patches, faulty_counts)):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                       f'{val}', ha='center', va='bottom', fontsize=9)
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '07_faulty_server_count.png'), dpi=300)
            plt.close()
            print(f"✓ Created 07_faulty_server_count.png")
        except Exception as e:
            print(f"✗ Failed to create faulty server chart: {e}")
        
        # 8. Services Hosted Distribution
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            total_services = [server_metrics[s]['total_services_hosted'] for s in scenarios]
            avg_per_server = [server_metrics[s]['avg_services_per_server'] for s in scenarios]
            
            x = np.arange(len(scenarios))
            width = 0.35
            
            ax.bar(x - width/2, total_services, width, label='Total', alpha=0.7, color='blue')
            ax2 = ax.twinx()
            ax2.plot(x, avg_per_server, marker='o', color='darkblue', linewidth=2, markersize=8, label='Avg/Server')
            
            ax.set_ylabel('Total Services Hosted', fontsize=11, color='blue')
            ax2.set_ylabel('Avg Services per Server', fontsize=11, color='darkblue')
            ax.set_title('Service Hosting Distribution', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.tick_params(axis='y', labelcolor='blue')
            ax2.tick_params(axis='y', labelcolor='darkblue')
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '08_services_hosted_distribution.png'), dpi=300)
            plt.close()
            print(f"✓ Created 08_services_hosted_distribution.png")
        except Exception as e:
            print(f"✗ Failed to create services hosted chart: {e}")
        
        # 9. Request Processing Throughput
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            requests_proc = [service_metrics[s]['total_requests_processed'] for s in scenarios]
            active_services = [service_metrics[s]['services_with_requests'] for s in scenarios]
            
            x = np.arange(len(scenarios))
            width = 0.35
            
            ax.bar(x - width/2, requests_proc, width, label='Requests Processed', alpha=0.7, color='purple')
            ax2 = ax.twinx()
            ax2.plot(x, active_services, marker='s', color='darkviolet', linewidth=2, markersize=8, label='Active Services')
            
            ax.set_ylabel('Requests Processed', fontsize=11, color='purple')
            ax2.set_ylabel('Number of Active Services', fontsize=11, color='darkviolet')
            ax.set_title('Request Processing Throughput', fontsize=13, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.tick_params(axis='y', labelcolor='purple')
            ax2.tick_params(axis='y', labelcolor='darkviolet')
            
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, '09_request_throughput.png'), dpi=300)
            plt.close()
            print(f"✓ Created 09_request_throughput.png")
        except Exception as e:
            print(f"✗ Failed to create throughput chart: {e}")
    
    def save_detailed_csv(self, outdir: str = "ComprehensiveAnalysis"):
        """Save detailed metrics to CSV files."""
        os.makedirs(outdir, exist_ok=True)
        
        server_metrics = self.extract_server_metrics()
        service_metrics = self.extract_service_metrics()
        impact_metrics = self.calculate_impact_metrics()
        
        # 1. Server Metrics CSV
        try:
            with open(os.path.join(outdir, 'server_metrics.csv'), 'w') as f:
                f.write("Scenario,Total_Servers,Faulty_Servers,Normal_Servers,Malicious_Percent,")
                f.write("CPU_Util_Avg,CPU_Util_Max,CPU_Util_Min,CPU_Util_StdDev,")
                f.write("Total_Services_Hosted,Avg_Services_Per_Server,Max_Services_On_Server,Fairness_Gini,")
                f.write("Total_Power_W,Avg_Power_Per_Server,Dropped_Requests,Rejected_Requests,")
                f.write("False_Reports,Delayed_Requests,Avg_Faults_Per_Server\n")
                
                for scenario, metrics in sorted(server_metrics.items()):
                    f.write(f"{scenario},")
                    f.write(f"{metrics['server_count']},{metrics['faulty_count']},{metrics['normal_count']},")
                    f.write(f"{metrics['malicious_percentage']:.2f},")
                    f.write(f"{metrics['cpu_util_avg']:.2f},{metrics['cpu_util_max']:.2f},{metrics['cpu_util_min']:.2f},{metrics['cpu_util_stdev']:.2f},")
                    f.write(f"{metrics['total_services_hosted']},{metrics['avg_services_per_server']:.2f},{metrics['max_services_on_server']},{metrics['service_distribution_fairness']:.4f},")
                    f.write(f"{metrics['total_power_consumption']:.0f},{metrics['avg_power_per_server']:.2f},")
                    f.write(f"{metrics['total_dropped_requests']},{metrics['total_rejected_requests']},")
                    f.write(f"{metrics['total_false_reports']},{metrics['total_delayed_requests']},{metrics['avg_faults_per_server']:.2f}\n")
            
            print(f"✓ Created server_metrics.csv")
        except Exception as e:
            print(f"✗ Failed to create server metrics CSV: {e}")
        
        # 2. Service Metrics CSV
        try:
            with open(os.path.join(outdir, 'service_metrics.csv'), 'w') as f:
                f.write("Scenario,Total_Services,Placed_Services,Unplaced_Services,Placement_Ratio,")
                f.write("Avg_Processing_Time_ms,Max_Processing_Time_ms,Total_Requests_Processed,")
                f.write("Avg_Requests_Per_Service,Active_Services,Idle_Services\n")
                
                for scenario, metrics in sorted(service_metrics.items()):
                    f.write(f"{scenario},")
                    f.write(f"{metrics['total_services']},{metrics['placed_services']},{metrics['unplaced_services']},")
                    f.write(f"{metrics['placement_ratio']:.2f},")
                    f.write(f"{metrics['avg_processing_time']:.2f},{metrics['max_processing_time']:.2f},")
                    f.write(f"{metrics['total_requests_processed']},{metrics['avg_requests_per_service']:.2f},")
                    f.write(f"{metrics['services_with_requests']},{metrics['idle_services']}\n")
            
            print(f"✓ Created service_metrics.csv")
        except Exception as e:
            print(f"✗ Failed to create service metrics CSV: {e}")
        
        # 3. Impact Metrics CSV
        if impact_metrics:
            try:
                with open(os.path.join(outdir, 'impact_metrics.csv'), 'w') as f:
                    f.write("Scenario,CPU_Util_Change_Percent,Service_Hosting_Reduction_Percent,")
                    f.write("Power_Consumption_Change_Percent,Total_Fault_Events,Avg_Impact_Per_Faulty_Server\n")
                    
                    for scenario, metrics in sorted(impact_metrics.items()):
                        f.write(f"{scenario},")
                        f.write(f"{metrics['cpu_utilization_change_percent']:+.2f},")
                        f.write(f"{metrics['service_hosting_reduction_percent']:.2f},")
                        f.write(f"{metrics['power_consumption_increase_percent']:+.2f},")
                        f.write(f"{metrics['total_fault_events']},")
                        f.write(f"{metrics['avg_impact_per_faulty_server']:.2f}\n")
                
                print(f"✓ Created impact_metrics.csv")
            except Exception as e:
                print(f"✗ Failed to create impact metrics CSV: {e}")


def calculate_gini(values):
    """Calculate Gini coefficient (0=perfect equality, 1=perfect inequality)."""
    if not values or len(values) < 2:
        return 0
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n


def main():
    """Main analysis entry point."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE BYZANTINE FAULT SIMULATION ANALYSIS".center(80))
    print("=" * 80 + "\n")
    
    metrics_files = {
        'Baseline': 'metrics_baseline.json',
        'Processing Delay Attack': 'metrics_delay_attack.json',
        'Request Dropping': 'metrics_request_dropping.json',
        'False Resource Reporting': 'metrics_false_reporting.json',
        'Selective Service Rejection': 'metrics_selective_rejection.json',
        'Mixed Byzantine Faults': 'metrics_mixed_faults.json',
    }
    
    # Check which files exist
    available_files = {k: v for k, v in metrics_files.items() if os.path.exists(v)}
    
    if not available_files:
        print("✗ No metric files found!")
        return
    
    print(f"Found {len(available_files)} metric files:\n")
    for scenario in available_files:
        print(f"  ✓ {scenario}")
    
    # Initialize analyzer
    print("\nInitializing analyzer...\n")
    analyzer = ComprehensiveAnalyzer(available_files)
    
    # Generate report
    print("Generating comprehensive analysis report...\n")
    report = analyzer.generate_comprehensive_report()
    print(report)
    
    # Save report
    with open('comprehensive_analysis_report.txt', 'w') as f:
        f.write(report)
    print(f"\n✓ Saved report to: comprehensive_analysis_report.txt")
    
    # Create visualizations
    print(f"\nGenerating visualization charts...")
    analyzer.create_visualizations('ComprehensiveAnalysis')
    
    # Save detailed CSVs
    print(f"\nSaving detailed metrics to CSV files...")
    analyzer.save_detailed_csv('ComprehensiveAnalysis')
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE".center(80))
    print("=" * 80)
    print("\nOutput files:")
    print("  - comprehensive_analysis_report.txt")
    print("  - ComprehensiveAnalysis/")
    print("    - 01_cpu_utilization.png")
    print("    - 02_service_placement_ratio.png")
    print("    - 03_power_consumption.png")
    print("    - 04_fault_events_breakdown.png")
    print("    - 05_fairness_gini.png")
    print("    - 06_impact_degradation.png")
    print("    - 07_faulty_server_count.png")
    print("    - 08_services_hosted_distribution.png")
    print("    - 09_request_throughput.png")
    print("    - server_metrics.csv")
    print("    - service_metrics.csv")
    print("    - impact_metrics.csv\n")


if __name__ == "__main__":
    main()
