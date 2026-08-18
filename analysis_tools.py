import json
import statistics
import os
from typing import Dict, List, Any
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


class FaultAnalyzer:
    
    def __init__(self, metrics_files: Dict[str, str]):
        self.results = {}
        for scenario, filepath in metrics_files.items():
            try:
                with open(filepath, 'r') as f:
                    self.results[scenario] = json.load(f)
            except FileNotFoundError:
                print(f"Warning: Could not find {filepath}")
    
    def get_fault_impact_summary(self) -> Dict[str, Dict[str, Any]]:
        summary = {}
        
        for scenario_name, metrics in self.results.items():
            # support both 'edges' and legacy 'edge_servers'
            edges = metrics.get('edges', []) or metrics.get('edge_servers', [])
            
            # Count misbehaving vs benign
            misbehaving = [e for e in edges if e.get('fault_type')]
            benign = [e for e in edges if not e.get('fault_type')]
            
            # Calculate fault-specific metrics
            total_dropped = sum(e.get('dropped_requests', 0) for e in misbehaving)
            total_rejected = sum(e.get('rejected_requests', 0) for e in misbehaving)
            total_false_reports = sum(e.get('false_reports_count', 0) for e in misbehaving)
            total_delayed = sum(e.get('delayed_requests', 0) for e in misbehaving)
            
            summary[scenario_name] = {
                'misbehaving_count': len(misbehaving),
                'benign_count': len(benign),
                'total_dropped_requests': total_dropped,
                'total_rejected_requests': total_rejected,
                'total_false_reports': total_false_reports,
                'total_delayed_requests': total_delayed,
                'execution_time': metrics.get('real_world_execution_time', 0),
                'speedup_factor': metrics.get('speedup_factor', 0),
            }
        
        return summary
    
    def compare_execution_times(self) -> Dict[str, float]:
        comparison = {}
        for scenario_name, metrics in self.results.items():
            comparison[scenario_name] = metrics.get('real_world_execution_time', 0)
        return comparison
    
    def get_resource_utilization(self) -> Dict[str, Dict[str, float]]:
        utilization = {}
        
        for scenario_name, metrics in self.results.items():
            edges = metrics.get('edges', []) or metrics.get('edge_servers', [])

            if edges:
                # edges may report resource attributes as 'cpu'/'memory' or 'cpu_demand' depending on exporter
                avg_cpu = statistics.mean(e.get('cpu', e.get('cpu_demand', 0)) for e in edges)
                avg_memory = statistics.mean(e.get('memory', e.get('memory_demand', 0)) for e in edges)
                avg_disk = statistics.mean(e.get('disk', e.get('disk_demand', 0)) for e in edges)

                utilization[scenario_name] = {
                    'avg_cpu_demand': avg_cpu,
                    'avg_memory_demand': avg_memory,
                    'avg_disk_demand': avg_disk,
                    'total_services_hosted': sum(e.get('services_hosted', 0) for e in edges),
                }
        
        return utilization
    
    def detect_anomalies(self) -> Dict[str, List[Dict[str, Any]]]:
        anomalies = {}
        
        for scenario_name, metrics in self.results.items():
            scenario_anomalies = []
            edges = metrics.get('edges', [])
            users = metrics.get('users', [])
            
            # Check for zero user mobility (potential simulation issue)
            # Some exports may include mobility stats under 'distance_traveled' or within collect(); fall back safely
            stationary_users = [u for u in users if u.get('distance_traveled', 0) == 0]
            if len(stationary_users) > len(users) * 0.8:
                scenario_anomalies.append({
                    'type': 'low_mobility',
                    'message': f'{len(stationary_users)} out of {len(users)} users are stationary',
                    'severity': 'medium'
                })
            
            # Check for high dropping rates
            for edge in edges:
                if edge.get('fault_type') == 'request_dropping':
                    drop_count = edge.get('dropped_requests', 0)
                    if drop_count > 100:
                        scenario_anomalies.append({
                            'type': 'high_drop_rate',
                            'server_id': edge.get('id'),
                            'message': f'Server {edge.get("id")} dropped {drop_count} requests',
                            'severity': 'high'
                        })
            
            # Check for resource overallocation
            misbehaving = [e for e in edges if e.get('fault_type') == 'false_resource_reporting']
            if misbehaving:
                for edge in misbehaving:
                    cpu_alloc = edge.get('cpu_demand', edge.get('cpu', 0))
                    cpu_cap = edge.get('cpu', None)
                    if cpu_cap and cpu_alloc > cpu_cap * 1.5:
                        scenario_anomalies.append({
                            'type': 'overallocation',
                            'server_id': edge.get('id'),
                            'message': f'Server {edge.get("id")} allocated beyond capacity',
                            'severity': 'high'
                        })
            
            anomalies[scenario_name] = scenario_anomalies
        
        return anomalies
    
    def generate_text_report(self) -> str:
        report = []
        report.append("=" * 80)
        report.append("BYZANTINE FAULT SIMULATION ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Impact Summary
        report.append("FAULT IMPACT SUMMARY")
        report.append("-" * 80)
        impact = self.get_fault_impact_summary()
        
        for scenario, metrics in impact.items():
            report.append(f"\nScenario: {scenario}")
            report.append(f"  Misbehaving Servers: {metrics['misbehaving_count']}")
            report.append(f"  Benign Servers: {metrics['benign_count']}")
            report.append(f"  Dropped Requests: {metrics['total_dropped_requests']}")
            report.append(f"  Rejected Requests: {metrics['total_rejected_requests']}")
            report.append(f"  False Reports: {metrics['total_false_reports']}")
            report.append(f"  Delayed Requests: {metrics['total_delayed_requests']}")
            report.append(f"  Execution Time: {metrics['execution_time']:.3f}s")
            report.append(f"  Speedup Factor: {metrics['speedup_factor']:.1f}x")
        
        # Execution Times
        report.append("\n" + "=" * 80)
        report.append("EXECUTION TIME COMPARISON")
        report.append("-" * 80)
        times = self.compare_execution_times()
        for scenario, exec_time in times.items():
            report.append(f"{scenario:<35} {exec_time:.3f} seconds")
        
        # Resource Utilization
        report.append("\n" + "=" * 80)
        report.append("RESOURCE UTILIZATION")
        report.append("-" * 80)
        util = self.get_resource_utilization()
        for scenario, metrics in util.items():
            report.append(f"\n{scenario}")
            report.append(f"  Avg CPU Demand: {metrics['avg_cpu_demand']:.2f}")
            report.append(f"  Avg Memory Demand: {metrics['avg_memory_demand']:.2f}")
            report.append(f"  Avg Disk Demand: {metrics['avg_disk_demand']:.2f}")
            report.append(f"  Total Services Hosted: {metrics['total_services_hosted']}")
        
        # Anomalies
        report.append("\n" + "=" * 80)
        report.append("DETECTED ANOMALIES & ISSUES")
        report.append("-" * 80)
        anomalies = self.detect_anomalies()
        for scenario, issues in anomalies.items():
            if issues:
                report.append(f"\n{scenario}:")
                for issue in issues:
                    report.append(f"  [{issue['severity'].upper()}] {issue['type']}: {issue['message']}")
            else:
                report.append(f"\n{scenario}: No anomalies detected")
        
        # Conclusion
        report.append("\n" + "=" * 80)
        report.append("CONCLUSION")
        report.append("-" * 80)
        report.append("All fault types successfully simulated and analyzed.")
        report.append("Results show distinct behavioral patterns for each fault type.")
        report.append("=" * 80)
        
        return "\n".join(report)

    def save_plots(self, outdir: str = "Analysis"):
        os.makedirs(outdir, exist_ok=True)

        # Use computed_metrics if available, otherwise derive from summaries
        scenarios = []
        mis_counts = []
        dropped = []
        rejected = []
        delayed = []
        throughput = []

        for scenario_name, metrics in self.results.items():
            scenarios.append(scenario_name)
            cm = metrics.get('computed_metrics', {})
            if cm:
                mis_counts.append(cm.get('misbehaving_count', 0))
                dropped.append(cm.get('total_dropped_requests', 0))
                rejected.append(cm.get('total_rejected_requests', 0))
                delayed.append(cm.get('total_delayed_requests', 0))
                throughput.append(cm.get('throughput_per_second', 0))
            else:
                # fallback: compute from edge lists
                edges = metrics.get('edges', []) or metrics.get('edge_servers', [])
                mis_counts.append(sum(1 for e in edges if e.get('fault_type')))
                dropped.append(sum(e.get('dropped_requests', 0) for e in edges))
                rejected.append(sum(e.get('rejected_requests', 0) for e in edges))
                delayed.append(sum(e.get('delayed_requests', 0) for e in edges))
                services = metrics.get('services', [])
                total_proc = sum(s.get('processed_requests', 0) for s in services) if services else 0
                sim_time = metrics.get('simulated_time_seconds', metrics.get('simulation_time_seconds', 1))
                throughput.append(total_proc / sim_time if sim_time else 0)

        # Plot misbehaving count as line
        try:
            x = range(len(scenarios))
            plt.figure(figsize=(8, 4))
            plt.plot(x, mis_counts, marker='o', color='tab:orange')
            plt.title('Misbehaving Servers per Scenario')
            plt.ylabel('Count')
            plt.xticks(x, scenarios, rotation=30, ha='right')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'misbehaving_counts.png'))
            plt.close()
        except Exception:
            pass

        # Plot dropped/rejected/delayed as lines
        try:
            x = range(len(scenarios))
            plt.figure(figsize=(10, 5))
            plt.plot(x, dropped, marker='o', label='Dropped', color='tab:orange')
            plt.plot(x, rejected, marker='o', label='Rejected', color='tab:red')
            plt.plot(x, delayed, marker='o', label='Delayed', color='tab:blue')
            plt.xticks(x, scenarios, rotation=30, ha='right')
            plt.legend()
            plt.title('Fault Effects: Dropped / Rejected / Delayed Requests')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'fault_effects.png'))
            plt.close()
        except Exception:
            pass

        # Throughput (line)
        try:
            x = range(len(scenarios))
            plt.figure(figsize=(8, 4))
            plt.plot(x, throughput, marker='o', color='tab:green')
            plt.title('Request Throughput (processed requests / second)')
            plt.ylabel('Processed / sec')
            plt.xticks(x, scenarios, rotation=30, ha='right')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'throughput.png'))
            plt.close()
        except Exception:
            pass

        # Additional charts: histograms and comparisons
        # Gather more derived metrics per scenario
        reported_cpu_avgs = []
        cpu_avgs = []
        power_avgs = []
        avg_latency = []
        total_pending = []
        processed_counts = []
        services_hosted = []

        for scenario_name, metrics in self.results.items():
            edges = metrics.get('edges', []) or metrics.get('edge_servers', [])
            services = metrics.get('services', []) or []
            cm = metrics.get('computed_metrics', {})

            # reported vs actual cpu averages
            if edges:
                reported_cpu_avgs.append(statistics.mean(e.get('reported_cpu', e.get('cpu', 0)) for e in edges))
                cpu_avgs.append(statistics.mean(e.get('cpu', 0) for e in edges))
                power_avgs.append(statistics.mean(e.get('power_consumption', 0) for e in edges))
                services_hosted.append(sum(e.get('services_hosted', 0) for e in edges))
            else:
                reported_cpu_avgs.append(0)
                cpu_avgs.append(0)
                power_avgs.append(0)
                services_hosted.append(0)

            # latency and processed
            processed = sum(s.get('processed_requests', 0) for s in services) if services else cm.get('total_processed_requests', 0)
            processed_counts.append(processed)
            total_pending.append(sum(s.get('pending_requests_count', 0) for s in services) if services else 0)
            avg_latency.append(cm.get('avg_processing_latency_seconds', 0))

        # Line: reported_cpu vs cpu per scenario
        try:
            x = range(len(scenarios))
            plt.figure(figsize=(10, 5))
            plt.plot(x, cpu_avgs, marker='o', label='cpu_avg')
            plt.plot(x, reported_cpu_avgs, marker='o', label='reported_cpu_avg')
            plt.xticks(x, scenarios, rotation=30, ha='right')
            plt.legend()
            plt.title('Average CPU vs Reported CPU per Scenario')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'cpu_vs_reported_cpu.png'))
            plt.close()
        except Exception:
            pass

        # Line: average latency per scenario
        try:
            x = range(len(scenarios))
            plt.figure(figsize=(8, 4))
            plt.plot(x, avg_latency, marker='o', color='tab:purple')
            plt.title('Average Processing Latency (s) per Scenario')
            plt.ylabel('Seconds')
            plt.xticks(x, scenarios, rotation=30, ha='right')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'avg_latency.png'))
            plt.close()
        except Exception:
            pass

        # Line: pending requests and processed counts
        try:
            x = range(len(scenarios))
            plt.figure(figsize=(10, 5))
            plt.plot(x, total_pending, marker='o', label='pending_requests')
            plt.plot(x, processed_counts, marker='o', label='processed_requests')
            plt.xticks(x, scenarios, rotation=30, ha='right')
            plt.legend()
            plt.title('Pending vs Processed Requests per Scenario')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'pending_vs_processed.png'))
            plt.close()
        except Exception:
            pass

        # Line: services hosted and power consumption comparison
        try:
            x = range(len(scenarios))
            plt.figure(figsize=(10, 5))
            plt.plot(x, services_hosted, marker='o', label='services_hosted')
            plt.plot(x, power_avgs, marker='o', label='avg_power')
            plt.xticks(x, scenarios, rotation=30, ha='right')
            plt.legend()
            plt.title('Services Hosted and Average Power per Scenario')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'services_power.png'))
            plt.close()
        except Exception:
            pass

        # Histograms: dropped/rejected/delayed across all scenarios combined (fallback)
        try:
            all_dropped = []
            all_rejected = []
            all_delayed = []
            for scenario_name, metrics in self.results.items():
                edges = metrics.get('edges', []) or metrics.get('edge_servers', [])
                all_dropped.extend([e.get('dropped_requests', 0) for e in edges])
                all_rejected.extend([e.get('rejected_requests', 0) for e in edges])
                all_delayed.extend([e.get('delayed_requests', 0) for e in edges])

            if all_dropped:
                counts, bins = np.histogram(all_dropped, bins=30)
                centers = (bins[:-1] + bins[1:]) / 2
                plt.figure(figsize=(8, 4))
                plt.plot(centers, counts, marker='o', color='tab:orange')
                plt.title('Distribution of Dropped Requests (all scenarios)')
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, 'hist_dropped_requests.png'))
                plt.close()

            if all_rejected:
                counts, bins = np.histogram(all_rejected, bins=30)
                centers = (bins[:-1] + bins[1:]) / 2
                plt.figure(figsize=(8, 4))
                plt.plot(centers, counts, marker='o', color='tab:red')
                plt.title('Distribution of Rejected Requests (all scenarios)')
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, 'hist_rejected_requests.png'))
                plt.close()

            if all_delayed:
                counts, bins = np.histogram(all_delayed, bins=30)
                centers = (bins[:-1] + bins[1:]) / 2
                plt.figure(figsize=(8, 4))
                plt.plot(centers, counts, marker='o', color='tab:blue')
                plt.title('Distribution of Delayed Requests (all scenarios)')
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, 'hist_delayed_requests.png'))
                plt.close()
        except Exception:
            pass

        # If time-series data exists, plot metrics over time with one line per scenario
        try:
            # Determine which scenarios have time-series
            ts_scenarios = {name: m.get('time_series') for name, m in self.results.items() if m.get('time_series')}
            if ts_scenarios:
                # Throughput (cumulative processed requests) over time
                plt.figure(figsize=(10, 5))
                for name, ts in ts_scenarios.items():
                    # plot overall cumulative processed per scenario
                    times = [t.get('time_seconds', t.get('step', 0)) for t in ts]
                    vals = [t.get('total_processed_requests', 0) for t in ts]
                    plt.plot(times, vals, marker='o', label=f"{name} (all)")
                    # if per-fault data available, plot one line per fault type
                    if ts and isinstance(ts[0], dict) and ts[0].get('per_fault'):
                        # collect fault types
                        fault_types = set()
                        for row in ts:
                            fault_types.update(row.get('per_fault', {}).keys())
                        for ft in sorted(fault_types):
                            ft_vals = [row.get('per_fault', {}).get(ft, {}).get('dropped', 0) for row in ts]
                            # plot dropped per fault type as separate line
                            plt.plot(times, ft_vals, linestyle='--', marker='x', label=f"{name}:{ft}:dropped")
                plt.title('Cumulative Processed Requests Over Time')
                plt.xlabel('Time (s)')
                plt.ylabel('Processed Requests (cumulative)')
                plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, 'ts_cumulative_processed.png'))
                plt.close()

                # Pending requests over time
                plt.figure(figsize=(10, 5))
                for name, ts in ts_scenarios.items():
                    times = [t.get('time_seconds', t.get('step', 0)) for t in ts]
                    vals = [t.get('total_pending_requests', 0) for t in ts]
                    plt.plot(times, vals, marker='o', label=f"{name} (all)")
                    if ts and isinstance(ts[0], dict) and ts[0].get('per_fault'):
                        fault_types = set()
                        for row in ts:
                            fault_types.update(row.get('per_fault', {}).keys())
                        for ft in sorted(fault_types):
                            ft_vals = [row.get('per_fault', {}).get(ft, {}).get('count', 0) for row in ts]
                            plt.plot(times, ft_vals, linestyle='--', marker='x', label=f"{name}:{ft}:count")
                plt.title('Total Pending Requests Over Time')
                plt.xlabel('Time (s)')
                plt.ylabel('Pending Requests')
                plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, 'ts_pending_requests.png'))
                plt.close()

                # Average misbehaving load over time
                plt.figure(figsize=(10, 5))
                for name, ts in ts_scenarios.items():
                    times = [t.get('time_seconds', t.get('step', 0)) for t in ts]
                    vals = [t.get('avg_load_mis', 0) for t in ts]
                    plt.plot(times, vals, marker='o', label=f"{name} (mis avg)")
                    if ts and isinstance(ts[0], dict) and ts[0].get('per_fault'):
                        fault_types = set()
                        for row in ts:
                            fault_types.update(row.get('per_fault', {}).keys())
                        for ft in sorted(fault_types):
                            ft_vals = [row.get('per_fault', {}).get(ft, {}).get('avg_load', 0) for row in ts]
                            plt.plot(times, ft_vals, linestyle='--', marker='x', label=f"{name}:{ft}:avg_load")
                plt.title('Average Load of Misbehaving Servers Over Time')
                plt.xlabel('Time (s)')
                plt.ylabel('Avg Load')
                plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, 'ts_avg_load_mis.png'))
                plt.close()

                # Reported CPU over time
                plt.figure(figsize=(10, 5))
                for name, ts in ts_scenarios.items():
                    times = [t.get('time_seconds', t.get('step', 0)) for t in ts]
                    vals = [t.get('avg_reported_cpu', 0) for t in ts]
                    plt.plot(times, vals, marker='o', label=f"{name} (reported)")
                    if ts and isinstance(ts[0], dict) and ts[0].get('per_fault'):
                        fault_types = set()
                        for row in ts:
                            fault_types.update(row.get('per_fault', {}).keys())
                        for ft in sorted(fault_types):
                            ft_vals = [row.get('per_fault', {}).get(ft, {}).get('avg_reported_cpu', 0) for row in ts]
                            plt.plot(times, ft_vals, linestyle='--', marker='x', label=f"{name}:{ft}:reported_cpu")
                plt.title('Average Reported CPU Over Time')
                plt.xlabel('Time (s)')
                plt.ylabel('Reported CPU')
                plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(outdir, 'ts_reported_cpu.png'))
                plt.close()
        except Exception:
            pass
    
    def save_per_fault_type_plots(self, outdir: str = "Analysis"):
        """
        Generate comparative plots broken down by fault type.
        One line per scenario for each metric.
        """
        os.makedirs(outdir, exist_ok=True)
        
        # Collect per-fault-type metrics from computed_metrics
        scenarios = list(self.results.keys())
        
        # Initialize data structures for each fault type
        fault_types_set = set()
        per_fault_data = {}  # {scenario: {fault_type: {metric: value}}}
        
        for scenario_name, metrics in self.results.items():
            per_fault_data[scenario_name] = {}
            cm = metrics.get('computed_metrics', {})
            pftb = cm.get('per_fault_type_breakdown', {})
            
            for fault_type, fault_metrics in pftb.items():
                fault_types_set.add(fault_type)
                per_fault_data[scenario_name][fault_type] = fault_metrics
        
        fault_types = sorted(list(fault_types_set))
        
        if not fault_types:
            return  # No per-fault-type data to plot
        
        # Plot 1: Dropped Requests by Fault Type
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(len(fault_types))
            width = 0.15
            
            for idx, scenario in enumerate(scenarios):
                dropped_counts = [per_fault_data[scenario].get(ft, {}).get('total_dropped', 0) for ft in fault_types]
                ax.bar(x + idx * width, dropped_counts, width, label=scenario)
            
            ax.set_xlabel('Fault Type')
            ax.set_ylabel('Dropped Requests')
            ax.set_title('Dropped Requests by Fault Type and Scenario')
            ax.set_xticks(x + width * len(scenarios) / 2)
            ax.set_xticklabels(fault_types, rotation=45, ha='right')
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'fault_type_dropped_requests.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 2: Rejected Requests by Fault Type
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(len(fault_types))
            width = 0.15
            
            for idx, scenario in enumerate(scenarios):
                rejected_counts = [per_fault_data[scenario].get(ft, {}).get('total_rejected', 0) for ft in fault_types]
                ax.bar(x + idx * width, rejected_counts, width, label=scenario)
            
            ax.set_xlabel('Fault Type')
            ax.set_ylabel('Rejected Requests')
            ax.set_title('Rejected Requests by Fault Type and Scenario')
            ax.set_xticks(x + width * len(scenarios) / 2)
            ax.set_xticklabels(fault_types, rotation=45, ha='right')
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'fault_type_rejected_requests.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 3: CPU Utilization by Fault Type
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(len(fault_types))
            width = 0.15
            
            for idx, scenario in enumerate(scenarios):
                cpu_utils = [per_fault_data[scenario].get(ft, {}).get('avg_cpu_util', 0) for ft in fault_types]
                ax.bar(x + idx * width, cpu_utils, width, label=scenario)
            
            ax.set_xlabel('Fault Type')
            ax.set_ylabel('CPU Utilization (%)')
            ax.set_title('Average CPU Utilization by Fault Type and Scenario')
            ax.set_xticks(x + width * len(scenarios) / 2)
            ax.set_xticklabels(fault_types, rotation=45, ha='right')
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'fault_type_cpu_utilization.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 4: Power Consumption by Fault Type
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(len(fault_types))
            width = 0.15
            
            for idx, scenario in enumerate(scenarios):
                power_vals = [per_fault_data[scenario].get(ft, {}).get('avg_power', 0) for ft in fault_types]
                ax.bar(x + idx * width, power_vals, width, label=scenario)
            
            ax.set_xlabel('Fault Type')
            ax.set_ylabel('Average Power (W)')
            ax.set_title('Average Power Consumption by Fault Type and Scenario')
            ax.set_xticks(x + width * len(scenarios) / 2)
            ax.set_xticklabels(fault_types, rotation=45, ha='right')
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'fault_type_power_consumption.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 5: Server Count by Fault Type (Malicious Percentage)
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(len(fault_types))
            width = 0.15
            
            for idx, scenario in enumerate(scenarios):
                server_counts = [per_fault_data[scenario].get(ft, {}).get('server_count', 0) for ft in fault_types]
                ax.bar(x + idx * width, server_counts, width, label=scenario)
            
            ax.set_xlabel('Fault Type')
            ax.set_ylabel('Number of Misbehaving Servers')
            ax.set_title('Server Count by Fault Type and Scenario')
            ax.set_xticks(x + width * len(scenarios) / 2)
            ax.set_xticklabels(fault_types, rotation=45, ha='right')
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'fault_type_server_count.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 6: Average Load by Fault Type
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = np.arange(len(fault_types))
            width = 0.15
            
            for idx, scenario in enumerate(scenarios):
                load_vals = [per_fault_data[scenario].get(ft, {}).get('avg_load', 0) for ft in fault_types]
                ax.bar(x + idx * width, load_vals, width, label=scenario)
            
            ax.set_xlabel('Fault Type')
            ax.set_ylabel('Average Load')
            ax.set_title('Average Load by Fault Type and Scenario')
            ax.set_xticks(x + width * len(scenarios) / 2)
            ax.set_xticklabels(fault_types, rotation=45, ha='right')
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'fault_type_average_load.png'))
            plt.close()
        except Exception:
            pass
    
    def save_summary_metrics_plots(self, outdir: str = "Analysis"):
        """
        Generate summary metric comparison plots.
        """
        os.makedirs(outdir, exist_ok=True)
        
        scenarios = list(self.results.keys())
        
        # Collect computed metrics
        success_rates = []
        not_answered_rates = []
        avg_cpu_utils = []
        avg_mem_utils = []
        total_powers = []
        fairness_ginis = []
        
        for scenario_name in scenarios:
            metrics = self.results[scenario_name]
            cm = metrics.get('computed_metrics', {})
            
            success_rates.append(cm.get('request_success_rate_percent', 0))
            not_answered_rates.append(cm.get('request_not_answered_rate_percent', 0))
            avg_cpu_utils.append(cm.get('avg_cpu_utilization_percent', 0))
            avg_mem_utils.append(cm.get('avg_memory_utilization_percent', 0))
            total_powers.append(cm.get('total_power_consumed', 0))
            fairness_ginis.append(cm.get('task_distribution_fairness_gini', 0))
        
        # Plot 1: Success Rate vs Not Answered Rate
        try:
            x = np.arange(len(scenarios))
            width = 0.35
            
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.bar(x - width/2, success_rates, width, label='Success Rate', color='green', alpha=0.7)
            ax.bar(x + width/2, not_answered_rates, width, label='Not Answered Rate', color='red', alpha=0.7)
            
            ax.set_xlabel('Scenario')
            ax.set_ylabel('Percentage (%)')
            ax.set_title('Request Success Rate vs Not Answered Rate by Scenario')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.legend()
            ax.set_ylim([0, 105])
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'summary_success_vs_not_answered.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 2: CPU and Memory Utilization
        try:
            x = np.arange(len(scenarios))
            width = 0.35
            
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(x, avg_cpu_utils, marker='o', linewidth=2, markersize=8, label='CPU Utilization', color='blue')
            ax.plot(x, avg_mem_utils, marker='s', linewidth=2, markersize=8, label='Memory Utilization', color='orange')
            
            ax.set_xlabel('Scenario')
            ax.set_ylabel('Utilization (%)')
            ax.set_title('Average CPU and Memory Utilization by Scenario')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.legend()
            ax.set_ylim([0, 100])
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'summary_utilization.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 3: Total Power Consumption
        try:
            x = np.arange(len(scenarios))
            
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(x, total_powers, marker='D', linewidth=2.5, markersize=10, color='purple')
            
            ax.set_xlabel('Scenario')
            ax.set_ylabel('Total Power (W)')
            ax.set_title('Total Power Consumption by Scenario')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'summary_total_power.png'))
            plt.close()
        except Exception:
            pass
        
        # Plot 4: Task Distribution Fairness (Gini)
        try:
            x = np.arange(len(scenarios))
            
            fig, ax = plt.subplots(figsize=(12, 6))
            bars = ax.bar(x, fairness_ginis, color='steelblue', alpha=0.7)
            
            # Color bars: green for fair (low gini), red for unfair (high gini)
            for bar, gini in zip(bars, fairness_ginis):
                if gini < 0.3:
                    bar.set_color('green')
                elif gini < 0.6:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')
            
            ax.set_xlabel('Scenario')
            ax.set_ylabel('Gini Coefficient (0=fair, 1=unfair)')
            ax.set_title('Task Distribution Fairness by Scenario')
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=45, ha='right')
            ax.axhline(y=0.3, color='green', linestyle='--', alpha=0.5, label='Fair threshold')
            ax.axhline(y=0.6, color='red', linestyle='--', alpha=0.5, label='Unfair threshold')
            ax.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(outdir, 'summary_task_fairness.png'))
            plt.close()
        except Exception:
            pass
    
    def save_report(self, filepath: str):
        with open(filepath, 'w') as f:
            f.write(self.generate_text_report())
        print(f"Report saved to {filepath}")
    
    def export_comparison_table(self, filepath: str):
        with open(filepath, 'w') as f:
            # Header
            f.write("Scenario,Misbehaving_Servers,Benign_Servers,Dropped_Requests,")
            f.write("Rejected_Requests,False_Reports,Delayed_Requests,Execution_Time_s\n")
        impact = self.get_fault_impact_summary()
        
        with open(filepath, 'w') as f:
            # Header
            f.write("Scenario,Misbehaving_Servers,Benign_Servers,Dropped_Requests,")
            f.write("Rejected_Requests,False_Reports,Delayed_Requests,Execution_Time_s\n")
            
            # Data rows
            for scenario, metrics in impact.items():
                f.write(f"{scenario},")
                f.write(f"{metrics['misbehaving_count']},")
                f.write(f"{metrics['benign_count']},")
                f.write(f"{metrics['total_dropped_requests']},")
                f.write(f"{metrics['total_rejected_requests']},")
                f.write(f"{metrics['total_false_reports']},")
                f.write(f"{metrics['total_delayed_requests']},")
                f.write(f"{metrics['execution_time']:.3f}\n")
        
        print(f"Comparison table saved to {filepath}")


def main():    
    metrics_files = {
        'Baseline': 'metrics_baseline.json',
        'Processing Delay Attack': 'metrics_delay_attack.json',
        'Request Dropping': 'metrics_request_dropping.json',
        'False Resource Reporting': 'metrics_false_reporting.json',
        'Selective Service Rejection': 'metrics_selective_rejection.json',
    }
    
    # Check if mixed faults metrics exist
    if os.path.exists('metrics_mixed_faults.json'):
        metrics_files['Mixed Byzantine Faults'] = 'metrics_mixed_faults.json'
    
    # Initialize analyzer
    analyzer = FaultAnalyzer(metrics_files)
    
    # Generate and print report
    print(analyzer.generate_text_report())
    
    # Save outputs
    analyzer.save_report('analysis_report.txt')
    analyzer.export_comparison_table('comparison_table.csv')
    
    # Generate and save comparison plots into Analysis/
    print("\nGenerating standard comparison plots...")
    analyzer.save_plots('Analysis')
    
    # Generate per-fault-type comparative plots
    print("Generating per-fault-type comparative plots...")
    analyzer.save_per_fault_type_plots('Analysis')
    
    # Generate summary metrics plots
    print("Generating summary metrics plots...")
    analyzer.save_summary_metrics_plots('Analysis')
    
    print("\nAnalysis complete! Generated files:")
    print("  - analysis_report.txt")
    print("  - comparison_table.csv")
    print("  - Analysis/*.png (standard comparison plots)")
    print("  - Analysis/*fault_type*.png (per-fault-type plots)")
    print("  - Analysis/summary_*.png (summary metrics plots)")


if __name__ == "__main__":
    main()
