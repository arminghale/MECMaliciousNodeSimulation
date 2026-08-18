import json
import time
import os
import traceback

from edge_sim_py import Simulator
from edge_sim_py.components import EdgeServer, User, Application, Service
import edge_sim_py.simulator as sim_module

from analysis_tools import FaultAnalyzer
from edge import FaultyEdgeServer

WHAT_SCENARIO_TO_RUN = [
    'baseline',
    'delay_attack',
    'false_reporting',
    'request_dropping',
    'selective_rejection',
    'mixed_fault'
]

# Import all datasets with fallback defaults

try:
    from dataset_baseline import DATASET as DATASET_BASE, USER_DEFINED_FUNCTIONS as USER_DEFINED_BASE, SERVICE_REQUESTS as SERVICE_REQUESTS_BASE
except (ImportError, SyntaxError) as e:
    print(f"Error loading DATASET_BASE: {e}")
    DATASET_BASE = {"edge_servers": [], "applications": [], "users": [], "services": []}
    USER_DEFINED_BASE = []
    SERVICE_REQUESTS_BASE = []

try:
    from dataset_delay_attack import DATASET as DATASET_DELAY, USER_DEFINED_FUNCTIONS as USER_DEFINED_DELAY, SERVICE_REQUESTS as SERVICE_REQUESTS_DELAY
except (ImportError, SyntaxError) as e:
    print(f"Error loading DATASET_DELAY: {e}")
    DATASET_DELAY = {"edge_servers": [], "applications": [], "users": [], "services": []}
    USER_DEFINED_DELAY = []
    SERVICE_REQUESTS_DELAY = []

try:
    from dataset_request_dropping import DATASET as DATASET_DROPS, USER_DEFINED_FUNCTIONS as USER_DEFINED_DROPS, SERVICE_REQUESTS as SERVICE_REQUESTS_DROPS
except (ImportError, SyntaxError) as e:
    print(f"Error loading DATASET_DROPS: {e}")
    DATASET_DROPS = {"edge_servers": [], "applications": [], "users": [], "services": []}
    USER_DEFINED_DROPS = []
    SERVICE_REQUESTS_DROPS = []

try:
    from dataset_false_reporting import DATASET as DATASET_FALSE, USER_DEFINED_FUNCTIONS as USER_DEFINED_FALSE, SERVICE_REQUESTS as SERVICE_REQUESTS_FALSE
except (ImportError, SyntaxError) as e:
    print(f"Error loading DATASET_FALSE: {e}")
    DATASET_FALSE = {"edge_servers": [], "applications": [], "users": [], "services": []}
    USER_DEFINED_FALSE = []
    SERVICE_REQUESTS_FALSE = []

try:
    from dataset_selective_rejection import DATASET as DATASET_SELECTIVE, USER_DEFINED_FUNCTIONS as USER_DEFINED_SELECTIVE, SERVICE_REQUESTS as SERVICE_REQUESTS_SELECTIVE
except (ImportError, SyntaxError) as e:
    print(f"Error loading DATASET_SELECTIVE: {e}")
    DATASET_SELECTIVE = {"edge_servers": [], "applications": [], "users": [], "services": []}
    USER_DEFINED_SELECTIVE = []
    SERVICE_REQUESTS_SELECTIVE = []

try:
    from dataset_mixed_faults import DATASET as DATASET_MIXED, USER_DEFINED_FUNCTIONS as USER_DEFINED_MIXED, SERVICE_REQUESTS as SERVICE_REQUESTS_MIXED
except (ImportError, SyntaxError) as e:
    print(f"Error loading DATASET_MIXED: {e}")
    DATASET_MIXED = {"edge_servers": [], "applications": [], "users": [], "services": []}
    USER_DEFINED_MIXED = []
    SERVICE_REQUESTS_MIXED = []


# # Time-series capture for analysis (populated by resource manager each tick)
# TIME_SERIES = {}
# CURRENT_SCENARIO = None

# Make custom class available to simulator
sim_module.FaultyEdgeServer = FaultyEdgeServer


def stop_condition(sim):
    return sim.schedule.steps >= 2000


def simple_resource_manager(parameters):
    from edge_sim_py.components import EdgeServer, Service

    # Iterate through all services looking for unprovisioned ones
    for service in Service.all():
        # Skip services already placed or being provisioned
        if service.server is not None or service.being_provisioned:
            continue
        
        # Find first available server with enough capacity
        for edge_server in EdgeServer.all():
            if edge_server.has_capacity_to_host(service=service):
                # Let EdgeSimPy handle the rest via Service.provision()
                service.provision(target_server=edge_server)
                break
                
                # # Blow code is for time-series analysis

                # # Normal server metrics
                # normal_avg_load = statistics.mean(getattr(e, 'load', 0) for e in normal_servers) if normal_servers else 0
                # normal_avg_cpu = statistics.mean(getattr(e, '_cpu_utilization', 0) for e in normal_servers) if normal_servers else 0
                # normal_avg_memory = statistics.mean(getattr(e, '_memory_utilization', 0) for e in normal_servers) if normal_servers else 0
                # normal_avg_reported_cpu = statistics.mean(getattr(e, 'reported_cpu', 0) for e in normal_servers) if normal_servers else 0
                # normal_total_power = sum(getattr(e, '_total_power_consumed', 0) for e in normal_servers)

                # # Calculate latencies
                # all_latencies = []
                # all_wait_times = []
                # for s in services_list:
                #     if hasattr(s, '_processed_latency_ticks_total') and hasattr(s, 'processed_requests'):
                #         if s.processed_requests > 0:
                #             avg_latency = s._processed_latency_ticks_total / s.processed_requests
                #             all_latencies.append(avg_latency * tick_duration)  # Convert to seconds
                #     if hasattr(s, '_total_wait_ticks') and hasattr(s, 'processed_requests'):
                #         if s.processed_requests > 0:
                #             avg_wait = s._total_wait_ticks / s.processed_requests
                #             all_wait_times.append(avg_wait * tick_duration)

                # avg_latency_seconds = statistics.mean(all_latencies) if all_latencies else 0
                # avg_wait_seconds = statistics.mean(all_wait_times) if all_wait_times else 0

                # # Throughput
                # throughput = (total_processed / simulated_seconds) if simulated_seconds > 0 else 0

                # snapshot = {
                #     'step': ts_step,
                #     'time_seconds': simulated_seconds,
                #     'total_processed_requests': total_processed,
                #     'total_pending_requests': total_pending,
                #     'total_dropped_requests': total_dropped,
                #     'total_rejected_requests': total_rejected,
                #     'total_not_answered_requests': total_not_answered,
                #     'throughput_requests_per_second': throughput,
                #     'avg_latency_seconds': avg_latency_seconds,
                #     'avg_wait_time_seconds': avg_wait_seconds,
                #     'normal_avg_load': normal_avg_load,
                #     'normal_avg_cpu_utilization': normal_avg_cpu,
                #     'normal_avg_memory_utilization': normal_avg_memory,
                #     'normal_avg_reported_cpu': normal_avg_reported_cpu,
                #     'normal_total_power': normal_total_power,
                #     'per_fault_type': per_fault_data,
                # }

                # if CURRENT_SCENARIO not in TIME_SERIES:
                #     TIME_SERIES[CURRENT_SCENARIO] = []
                # TIME_SERIES[CURRENT_SCENARIO].append(snapshot)


def run_scenario(scenario_name, dataset, output_file, user_functions=None, service_requests=None):
    print(f"\n{'='*70}")
    print(f"Starting Scenario: {scenario_name}")
    print(f"{'='*70}")

    try:
        sim = Simulator(
            stopping_criterion=stop_condition,
            resource_management_algorithm=simple_resource_manager,
            tick_duration=50,
            tick_unit="seconds",
            user_defined_functions=user_functions or [],
        )

        sim.initialize(dataset)

        # Convert EdgeServer instances with a fault_type attribute into FaultyEdgeServer
        try:
            
            # get all current edge server agent instances
            edge_agents = EdgeServer.all()
            for agent in list(edge_agents):
                # Check for dataset-provided fault markers (either attribute or in attributes dict)
                fault = None
                if hasattr(agent, 'fault_type') and getattr(agent, 'fault_type'):
                    fault = getattr(agent, 'fault_type')
                if fault:
                    try:
                        # Change the instance class to FaultyEdgeServer so methods are available
                        agent.__class__ = FaultyEdgeServer
                        # Ensure fault metadata exists on the instance
                        agent.fault_type = fault
                        if not hasattr(agent, 'fault_config'):
                            agent.fault_config = {}
                        # Initialize fault counters if missing
                        for metric in ('dropped_requests', 'rejected_requests', 'false_reports_count', 'delayed_requests'):
                            if not hasattr(agent, metric):
                                setattr(agent, metric, 0)
                    except Exception:
                        # Keep going if individual conversion fails
                        pass
        except Exception:
            pass

        # Map module-level SERVICE_REQUESTS into Service.pending_requests at runtime (round-robin)
        try:
            if service_requests and len(service_requests) > 0:
                
                services = Service.all()
                if services and len(services) > 0:
                    for idx, req in enumerate(service_requests):
                        svc = services[idx % len(services)]
                        if not hasattr(svc, 'pending_requests') or svc.pending_requests is None:
                            svc.pending_requests = []
                        req_attrs = req.get('attributes') if isinstance(req, dict) else req
                        # annotate enqueue step for later latency calculation
                        try:
                            enqueue_step = sim.schedule.steps if hasattr(sim, 'schedule') and hasattr(sim.schedule, 'steps') else 0
                            if isinstance(req_attrs, dict) and 'enqueued_step' not in req_attrs:
                                req_attrs['enqueued_step'] = enqueue_step
                        except Exception:
                            pass
                        svc.pending_requests.append(req_attrs)
                        # initialize processed counter if missing
                        if not hasattr(svc, 'processed_requests'):
                            svc.processed_requests = 0
        except Exception:
            pass

        # Measure execution time
        start_time = time.time()
        # # enable time-series capture for this scenario
        # try:
        #     global CURRENT_SCENARIO, TIME_SERIES
        #     CURRENT_SCENARIO = scenario_name
        #     TIME_SERIES[scenario_name] = []
        # except Exception:
        #     pass

        sim.run_model()
        
        # # disable time-series capture
        # try:
        #     CURRENT_SCENARIO = None
        # except Exception:
        #     pass
        elapsed_time = time.time() - start_time
        
        # Collect metrics from EdgeSimPy's built-in agent collection
        edge_metrics = []
        user_metrics = []
        app_metrics = []
        service_metrics = []
        faulty_count = 0
        normal_count = 0
        
        try:
            # EdgeSimPy stores simulation data in agent_metrics
            # which is populated by calling collect() on each agent during simulation
            
            # Collect edge server metrics
            
            
            for edge_server in EdgeServer.all():
                edge_m = {
                    "id": edge_server.id,
                    "cpu": edge_server.cpu,
                    "memory": edge_server.memory,
                    "disk": edge_server.disk,
                    "cpu_demand": edge_server.cpu_demand,
                    "memory_demand": edge_server.memory_demand,
                    "disk_demand": edge_server.disk_demand,
                    "load": getattr(edge_server, 'load', 0),
                }
                
                # Add fault type if present (from FaultyEdgeServer)
                if hasattr(edge_server, 'fault_type') and edge_server.fault_type:
                    edge_m['fault_type'] = edge_server.fault_type
                    faulty_count += 1
                else:
                    normal_count += 1
                
                # Get data from last collect() call if available
                if hasattr(edge_server, 'collect'):
                    collected = edge_server.collect()
                    edge_m.update(collected)
                
                # Services hosted on this server
                if hasattr(edge_server, 'services'):
                    edge_m['services_hosted'] = len(edge_server.services)
                
                edge_metrics.append(edge_m)
            
            # Collect user metrics
            for user in User.all():
                user_m = {"id": user.id}
                
                if hasattr(user, 'collect'):
                    user_m.update(user.collect())
                
                user_metrics.append(user_m)
            
            # Collect application metrics
            for app in Application.all():
                app_m = {
                    "id": app.id,
                    "cpu_demand": app.cpu_demand,
                    "memory_demand": app.memory_demand,
                }
                
                if hasattr(app, 'collect'):
                    app_m.update(app.collect())
                
                app_metrics.append(app_m)
            
            # Collect service metrics
            for service in Service.all():
                svc_m = {
                    "id": service.id,
                    "cpu_demand": service.cpu_demand,
                    "memory_demand": service.memory_demand,
                    "server": service.server.id if service.server else None,
                    "available": service._available if hasattr(service, '_available') else False,
                }
                
                if hasattr(service, 'collect'):
                    svc_m.update(service.collect())
                
                service_metrics.append(svc_m)
        
        except Exception as e:
            print(f"Warning: Metrics collection had issues: {e}")
            
            traceback.print_exc()
        
        simulated_time = sim.schedule.steps * sim.tick_duration
        
        # Print summary
        print(f"\nSimulation Complete:")
        print(f"  Steps: {sim.schedule.steps}")
        print(f"  Edge Servers: {len(edge_metrics)} (Faulty: {faulty_count}, Normal: {normal_count})")
        print(f"  Users: {len(user_metrics)}")
        print(f"  Applications: {len(app_metrics)}")
        print(f"  Services: {len(service_metrics)}")
        print(f"  Exec Time: {elapsed_time:.3f}s")
        
        # Save comprehensive metrics
        metrics_summary = {
            "scenario_name": scenario_name,
            "simulation_time_steps": sim.schedule.steps,
            "simulated_time_seconds": simulated_time,
            "real_world_execution_time": elapsed_time,
            "component_counts": {
                "edge_servers": len(edge_metrics),
                "faulty_servers": faulty_count,
                "normal_servers": normal_count,
                "users": len(user_metrics),
                "applications": len(app_metrics),
                "services": len(service_metrics),
            },
            "edge_servers": edge_metrics,
            "edges": edge_metrics,
            # include captured time-series if present
            # "time_series": TIME_SERIES.get(scenario_name, []),
            "users": user_metrics,
            "applications": app_metrics,
            "services": service_metrics,
        }

        # Compute basic summary metrics from collected data
        try:
            computed = {}
            
            # Misbehaving server count
            faulty_servers = [e for e in edge_metrics if e.get('fault_type')]
            computed['faulty_count'] = len(faulty_servers)
            computed['faulty_percent'] = (len(faulty_servers) / len(edge_metrics) * 100) if edge_metrics else 0
            
            # Average load by server type
            mis_loads = [e.get('load', 0) for e in faulty_servers]
            ben_loads = [e.get('load', 0) for e in edge_metrics if not e.get('fault_type')]
            
            computed['avg_load_faulty'] = sum(mis_loads) / len(mis_loads) if mis_loads else 0
            computed['avg_load_normal'] = sum(ben_loads) / len(ben_loads) if ben_loads else 0
            computed['avg_load_delta'] = computed['avg_load_faulty'] - computed['avg_load_normal']
            
            # Services provisioned
            provisioned_services = [s for s in service_metrics if s.get('server')]
            computed['total_services'] = len(service_metrics)
            computed['services_provisioned'] = len(provisioned_services)
            computed['services_not_provisioned'] = len(service_metrics) - len(provisioned_services)
            
            # Per-fault-type analysis
            computed['per_fault_type_breakdown'] = {}
            fault_types_seen = set(e.get('fault_type') for e in edge_metrics if e.get('fault_type'))
            
            for fault_type in sorted(fault_types_seen):
                fault_servers = [e for e in edge_metrics if e.get('fault_type') == fault_type]
                if fault_servers:
                    computed['per_fault_type_breakdown'][fault_type] = {
                        'server_count': len(fault_servers),
                        'avg_load': sum(e.get('load', 0) for e in fault_servers) / len(fault_servers),
                        'services_hosted': sum(e.get('services_hosted', 0) for e in fault_servers),
                    }

        except Exception as e:
            print(f"Warning: Computed metrics calculation failed: {e}")
            computed = {}

        metrics_summary['computed_metrics'] = computed
        
        with open(output_file, "w") as f:
            json.dump(metrics_summary, f, indent=2)
        
        print(f"Metrics saved to '{output_file}'")
        return metrics_summary
        
    except Exception as e:
        print(f"ERROR in scenario {scenario_name}: {e}")
        traceback.print_exc()
        return None


def main():    
    results = {}
    
    # Scenario 0: Baseline
    if 'baseline' in WHAT_SCENARIO_TO_RUN:
        result = run_scenario(
            "Baseline",
            DATASET_BASE,
            "metrics_baseline.json",
            user_functions=USER_DEFINED_BASE,
            service_requests=SERVICE_REQUESTS_BASE,
        )
        if result:
            results['baseline'] = result

    # Scenario 1: Processing Delay Attack
    if 'delay_attack' in WHAT_SCENARIO_TO_RUN:
        result = run_scenario(
            "Processing Delay Attack",
            DATASET_DELAY,
            "metrics_delay_attack.json",
            user_functions=USER_DEFINED_DELAY,
            service_requests=SERVICE_REQUESTS_DELAY,
        )
        if result:
            results['delay_attack'] = result
        
    # Scenario 2: Request Dropping
    if 'request_dropping' in WHAT_SCENARIO_TO_RUN:
        result = run_scenario(
            "Request Dropping",
            DATASET_DROPS,
            "metrics_request_dropping.json",
            user_functions=USER_DEFINED_DROPS,
            service_requests=SERVICE_REQUESTS_DROPS,
        )
        if result:
            results['request_dropping'] = result
        
    # Scenario 3: False Resource Reporting
    if 'false_reporting' in WHAT_SCENARIO_TO_RUN:
        result = run_scenario(
            "False Resource Reporting",
            DATASET_FALSE,
            "metrics_false_reporting.json",
            user_functions=USER_DEFINED_FALSE,
            service_requests=SERVICE_REQUESTS_FALSE,
        )
        if result:
            results['false_reporting'] = result
        
    # Scenario 4: Selective Service Rejection
    if 'selective_rejection' in WHAT_SCENARIO_TO_RUN:
        result = run_scenario(
            "Selective Service Rejection",
            DATASET_SELECTIVE,
            "metrics_selective_rejection.json",
            user_functions=USER_DEFINED_SELECTIVE,
            service_requests=SERVICE_REQUESTS_SELECTIVE,
        )
        if result:
            results['selective_rejection'] = result
    
    # Scenario 5: Mixed Byzantine Faults
    if 'mixed_fault' in WHAT_SCENARIO_TO_RUN:
        result = run_scenario(
            "Mixed Byzantine Faults",
            DATASET_MIXED,
            "metrics_mixed_faults.json",
            user_functions=USER_DEFINED_MIXED,
            service_requests=SERVICE_REQUESTS_MIXED,
        )
        if result:
            results['mixed_faults'] = result

    # Generate comparative analysis
    if results:
        # Summary table
        print(f"{'Scenario':<30} {'Edges':<10} {'Faulty.':<10} {'Users':<10} {'Apps':<10} {'Services':<10} {'Exec Time':<12}")
        print("-" * 92)
        for scenario_name, metrics in results.items():
            counts = metrics.get('component_counts', {})
            print(f"{scenario_name:<30} {counts.get('edge_servers', 0):<10} "
                  f"{counts.get('faulty_servers', 0):<10} "
                  f"{counts.get('users', 0):<10} "
                  f"{counts.get('applications', 0):<10} "
                  f"{counts.get('services', 0):<10} "
                  f"{metrics.get('real_world_execution_time', 0):.3f}s")
    
    # Save comparative summary
    comparative_summary = {
        "test_suite": "Fault Type Comparison",
        "scenarios_tested": len(results),
        "scenario_results": results
    }
    
    with open("test_suite_summary.json", "w") as f:
        json.dump(comparative_summary, f, indent=2)
        
    # Run analysis with new visualization functions
    try:    
        # Create Analysis directory if it doesn't exist
        os.makedirs('Analysis', exist_ok=True)
        
        metrics_files = {
            'Baseline': 'metrics_baseline.json',
            'Processing Delay Attack': 'metrics_delay_attack.json',
            'Request Dropping': 'metrics_request_dropping.json',
            'False Resource Reporting': 'metrics_false_reporting.json',
            'Selective Service Rejection': 'metrics_selective_rejection.json',
        }
        
        analyzer = FaultAnalyzer(metrics_files)
        
        # Generate text report
        analyzer.save_report('analysis_report.txt')
        analyzer.export_comparison_table('comparison_table.csv')
        
        # Generate all visualization plots
        analyzer.save_plots('Analysis')
        analyzer.save_per_fault_type_plots('Analysis')
        analyzer.save_summary_metrics_plots('Analysis')
        
    except Exception as e:
        print(f"Analysis generation error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
