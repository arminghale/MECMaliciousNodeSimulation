import json
import time
import traceback
import statistics

from edge_sim_py import Simulator
from edge_sim_py.components import EdgeServer, User, Application, Service, ContainerRegistry, ContainerLayer

from v2_edge import FaultyEdgeServer
from v2_mobility import AVAILABLE_MOBILITY_MODELS
from v2_dataset import create_dataset, USER_DEFINED_FUNCTIONS

SCENARIOS_TO_RUN = [
    # 'baseline',
    'delay_attack',
    # 'false_reporting',
    # 'request_dropping',
    # 'selective_rejection',
    # 'mixed_fault',
]

SCENARIO_CONFIGS = {
    'baseline': {
        'module': 'v2_dataset',
        'malicious_percentage': 0.0,
        'fault_type': None,
        'output_file': 'metrics_baseline.json',
    },
    'delay_attack': {
        'module': 'v2_dataset',
        'malicious_percentage': 10.0,
        'fault_type': 'processing_delay_attack',
        'output_file': 'metrics_delay_attack.json',
    },
    'false_reporting': {
        'module': 'v2_dataset',
        'malicious_percentage': 10.0,
        'fault_type': 'false_resource_reporting',
        'output_file': 'metrics_false_reporting.json',
    },
    'request_dropping': {
        'module': 'v2_dataset',
        'malicious_percentage': 10.0,
        'fault_type': 'request_dropping',
        'output_file': 'metrics_request_dropping.json',
    },
    'selective_rejection': {
        'module': 'v2_dataset',
        'malicious_percentage': 10.0,
        'fault_type': 'selective_service_rejection',
        'output_file': 'metrics_selective_rejection.json',
    },
    'mixed_fault': {
        'module': 'v2_dataset',
        'malicious_percentage': 20.0,
        'fault_type': 'mixed_Byzantine',  # Multiple fault types
        'output_file': 'metrics_mixed_faults.json',
    },
}

def load_dataset(scenario_name):
       
    config = SCENARIO_CONFIGS.get(scenario_name)
    if not config:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    
    try:
        dataset, service_requests, metadata = create_dataset(
            malicious_percentage=config['malicious_percentage'],
            fault_type=config['fault_type'],
        )
        
        return dataset, service_requests, USER_DEFINED_FUNCTIONS
    
    except Exception as e:
        raise RuntimeError(f"Error creating dataset for {scenario_name}: {e}")

def create_stop_condition(max_steps=2000):
    def stop_condition(sim):
        # Stop when:
        # 1. All services are provisioned, OR
        # 2. Maximum steps reached
        try:
            all_services = Service.all()
            if not all_services:
                return True 
            
            all_placed = all(service.server is not None for service in all_services)
            max_steps_reached = sim.schedule.steps >= max_steps
            
            return all_placed or max_steps_reached
        except Exception:
            return sim.schedule.steps >= max_steps
    
    return stop_condition

def create_resource_manager():
    def simple_resource_manager(parameters):
        """
        Simple first-fit resource manager: place all unplaced services.
        WORKAROUND: Directly place services on servers (skip async provisioning).
        """
        try:
            # Get all unplaced services
            unplaced_services = [s for s in Service.all() 
                                if s.server is None]
            
            if not unplaced_services:
                return
            
            # Get all edge servers
            all_servers = list(EdgeServer.all())
            if not all_servers:
                return
            
            # Attempt to place each unplaced service
            for service in unplaced_services:
                # Initialize service metrics if needed
                if not hasattr(service, 'requests_processed'):
                    service.requests_processed = 0
                
                # Find a suitable server
                for server in all_servers:
                    try:
                        # Check capacity
                        available_cpu = server.cpu - server.cpu_demand
                        available_memory = server.memory - server.memory_demand
                        available_disk = server.disk - server.disk_demand if hasattr(server, 'disk_demand') else server.disk
                        
                        needs_cpu = service.cpu_demand
                        needs_memory = service.memory_demand
                        needs_disk = service.disk_demand if hasattr(service, 'disk_demand') else 0
                        
                        if (available_cpu >= needs_cpu and 
                            available_memory >= needs_memory and
                            available_disk >= needs_disk):
                            # WORKAROUND: Directly place service instead of async provision
                            # This bypasses the complex network-based layer downloading
                            service.server = server
                            service._available = True
                            service.being_provisioned = False
                            server.services.append(service)
                            server.cpu_demand += needs_cpu
                            server.memory_demand += needs_memory
                            server.disk_demand = getattr(server, 'disk_demand', 0) + needs_disk
                            break
                    except Exception:
                        # Try next server if this one fails
                        continue
        except Exception as e:
            # Silently handle errors to keep simulation running
            pass
    
    return simple_resource_manager


def populate_registry_layers():
    """Populate registry servers with all available container layers.
    
    Must be called right after sim.initialize() and before sim.run_model()
    """
    registries = list(ContainerRegistry.all())
    all_layers = list(ContainerLayer.all())
    
    if registries and all_layers:
        for registry in registries:
            if registry.server:
                # Pre-populate the registry server's container_layers
                # This allows EdgeServer.step() to find and download layers
                registry.server.container_layers = all_layers.copy()
    
    return len(registries), len(all_layers)


def convert_to_faulty_servers(fault_type):
    """
    Convert EdgeServer instances to FaultyEdgeServer instances if marked as faulty.

    """
    conversion_count = 0
    
    try:
        edge_agents = list(EdgeServer.all())
        
        for agent in edge_agents:
            fault = None
            fault_config = {}
            
            if hasattr(agent, 'fault_type') and agent.fault_type:
                fault = agent.fault_type
            
            elif hasattr(agent, 'attributes') and isinstance(agent.attributes, dict):
                fault = agent.attributes.get('fault_type')
                fault_config = agent.attributes.get('fault_config', {})
            
            if fault:
                try:
                    agent.__class__ = FaultyEdgeServer
                    
                    agent.fault_type = fault
                    agent.fault_config = fault_config
                    
                    # Initialize all fault-related metrics
                    for metric in ['dropped_requests', 'rejected_requests', 
                                 'false_reports_count', 'delayed_requests',
                                 'requests_received', 'requests_processed', 'requests_failed']:
                        if not hasattr(agent, metric):
                            setattr(agent, metric, 0)
                    
                    # Initialize power profile if needed
                    if not hasattr(agent, 'power_profile'):
                        agent.power_profile = {
                            'idle_power': 20,
                            'peak_power': 200,
                        }
                    if not hasattr(agent, 'power_consumption'):
                        agent.power_consumption = 0
                    
                    conversion_count += 1
                
                except Exception as e:
                    print(f"  Warning: Could not convert server {getattr(agent, 'id', '?')}: {e}")
                    continue
    
    except Exception as e:
        print(f"  Warning: Conversion process failed: {e}")
    
    return conversion_count

def collect_metrics():
    edge_metrics = []
    user_metrics = []
    app_metrics = []
    service_metrics = []
    faulty_count = 0
    normal_count = 0
    
    # Collect edge server metrics
    try:
        for edge_server in EdgeServer.all():
            edge_m = {
                "id": edge_server.id,
                "name": getattr(edge_server, 'name', f"server_{edge_server.id}"),
                "cpu_capacity": edge_server.cpu,
                "memory_capacity": edge_server.memory,
                "disk_capacity": edge_server.disk,
                "cpu_demand": getattr(edge_server, 'cpu_demand', 0),
                "memory_demand": getattr(edge_server, 'memory_demand', 0),
                "disk_demand": getattr(edge_server, 'disk_demand', 0),
                "services_hosted": len(edge_server.services) if hasattr(edge_server, 'services') else 0,
                "load": getattr(edge_server, 'load', 0),
                "utilization_percent": (getattr(edge_server, 'cpu_demand', 0) / edge_server.cpu * 100) if edge_server.cpu > 0 else 0,
                "power_consumption": getattr(edge_server, 'power_consumption', 0),
            }
            
            if hasattr(edge_server, 'collect') and callable(edge_server.collect):
                try:
                    collected = edge_server.collect()
                    if isinstance(collected, dict):
                        edge_m.update(collected)
                except Exception as e:
                    pass
            
            if edge_m.get('fault_type'):
                faulty_count += 1
            else:
                normal_count += 1
            
            edge_metrics.append(edge_m)
    
    except Exception as e:
        print(f"Warning: Error collecting edge server metrics: {e}")
    
    # Collect user metrics
    try:
        for user in User.all():
            user_m = {
                "id": user.id,
                "coordinates": getattr(user, 'coordinates', [0, 0]),
                "active": getattr(user, 'active', True),
            }
            
            if hasattr(user, 'collect') and callable(user.collect):
                try:
                    collected = user.collect()
                    if isinstance(collected, dict):
                        user_m.update(collected)
                except Exception:
                    pass
            
            user_metrics.append(user_m)
    
    except Exception as e:
        print(f"Warning: Error collecting user metrics: {e}")
    
    # Collect application metrics
    try:
        for app in Application.all():
            app_m = {
                "id": app.id,
                "cpu_demand": app.cpu_demand,
                "memory_demand": app.memory_demand,
                "priority": getattr(app, 'priority', 0),
            }
            
            if hasattr(app, 'collect') and callable(app.collect):
                try:
                    collected = app.collect()
                    if isinstance(collected, dict):
                        app_m.update(collected)
                except Exception:
                    pass
            
            app_metrics.append(app_m)
    
    except Exception as e:
        print(f"Warning: Error collecting application metrics: {e}")
    
    # Collect service metrics
    try:
        for service in Service.all():
            svc_m = {
                "id": service.id,
                "name": getattr(service, 'name', f"service_{service.id}"),
                "cpu_demand": service.cpu_demand,
                "memory_demand": service.memory_demand,
                "server": service.server.id if service.server else None,
                "server_name": service.server.name if service.server and hasattr(service.server, 'name') else None,
                "available": service._available if hasattr(service, '_available') else False,
                "processing_time": getattr(service, 'processing_time', 0),
                "requests_processed": getattr(service, 'requests_processed', 0),
            }
            
            if hasattr(service, 'collect') and callable(service.collect):
                try:
                    collected = service.collect()
                    if isinstance(collected, dict):
                        svc_m.update(collected)
                except Exception:
                    pass
            
            service_metrics.append(svc_m)
    
    except Exception as e:
        print(f"Warning: Error collecting service metrics: {e}")
    
    return {
        'edge_metrics': edge_metrics,
        'user_metrics': user_metrics,
        'app_metrics': app_metrics,
        'service_metrics': service_metrics,
        'faulty_count': faulty_count,
        'normal_count': normal_count,
    }


def run_scenario(scenario_name):
    """Run a single simulation scenario."""
    print(f"\n{'='*70}")
    print(f"Scenario: {scenario_name.upper()}")
    print(f"{'='*70}")
    
    config = SCENARIO_CONFIGS[scenario_name]
    
    try:
        # Load dataset
        print("Loading dataset...", end=" ")
        dataset, service_requests, user_functions = load_dataset(scenario_name)
        print(f"OK")
        
        # Register all mobility models
        print("Registering user-defined functions...", end=" ")
        all_functions = user_functions + list(AVAILABLE_MOBILITY_MODELS.values())
        print(f"OK ({len(all_functions)} functions)")
        
        # Create simulator
        print("Initializing simulator...", end=" ")
        sim = Simulator(
            stopping_criterion=create_stop_condition(max_steps=500),
            resource_management_algorithm=create_resource_manager(),
            tick_duration=1,
            tick_unit="seconds",
            user_defined_functions=all_functions,
        )
        print(f"OK")
        
        # Initialize with dataset
        print("Loading dataset into simulator...", end=" ")
        sim.initialize(dataset)
        print(f"OK")
        
        # Populate registry servers with container layers for downloading
        print("Populating container registries...", end=" ")
        reg_count, layer_count = populate_registry_layers()
        print(f"OK ({reg_count} registries, {layer_count} layers)")
        
        # Convert faulty servers
        print("Converting to FaultyEdgeServer...", end=" ")
        conversion_count = convert_to_faulty_servers(config['fault_type'])
        print(f"OK ({conversion_count} servers)")
        
        # Run simulation
        print("Running simulation...", end=" ")
        start_time = time.time()
        sim.run_model()
        elapsed_time = time.time() - start_time
        print(f"OK ({elapsed_time:.2f}s)")
        
        # Collect metrics
        print("Collecting metrics...", end=" ")
        metrics_data = collect_metrics()
        print(f"OK")
        
        # Prepare output
        simulated_time = sim.schedule.steps * sim.tick_duration
        
        output = {
            "scenario_name": scenario_name,
            "config": config,
            "simulation_stats": {
                "timesteps": sim.schedule.steps,
                "simulated_seconds": simulated_time,
                "real_world_seconds": elapsed_time,
                "speedup_factor": simulated_time / elapsed_time if elapsed_time > 0 else 0,
            },
            "component_counts": {
                "edge_servers": len(metrics_data['edge_metrics']),
                "faulty_servers": metrics_data['faulty_count'],
                "normal_servers": metrics_data['normal_count'],
                "users": len(metrics_data['user_metrics']),
                "applications": len(metrics_data['app_metrics']),
                "services": len(metrics_data['service_metrics']),
            },
            "edge_servers": metrics_data['edge_metrics'],
            "edges": metrics_data['edge_metrics'],  # Alias for compatibility
            "users": metrics_data['user_metrics'],
            "applications": metrics_data['app_metrics'],
            "services": metrics_data['service_metrics'],
        }
        
        # Compute summary statistics
        try:
            edge_metrics = metrics_data['edge_metrics']
            service_metrics = metrics_data['service_metrics']
            user_metrics = metrics_data['user_metrics']
            faulty_servers = [e for e in edge_metrics if e.get('fault_type')]
            normal_servers = [e for e in edge_metrics if not e.get('fault_type')]
            
            output['summary_stats'] = {
                'faulty_count': len(faulty_servers),
                'normal_count': len(normal_servers),
                'total_dropped_requests': sum(e.get('dropped_requests', 0) for e in faulty_servers),
                'total_rejected_requests': sum(e.get('rejected_requests', 0) for e in faulty_servers),
                'total_false_reports': sum(e.get('false_reports_count', 0) for e in faulty_servers),
                'total_delayed_requests': sum(e.get('delayed_requests', 0) for e in faulty_servers),
                'total_services_hosted': sum(e.get('services_hosted', 0) for e in edge_metrics),
                'avg_cpu_utilization': statistics.mean([e.get('utilization_percent', 0) for e in edge_metrics]) if edge_metrics else 0,
                'avg_power_consumption': statistics.mean([e.get('power_consumption', 0) for e in edge_metrics]) if edge_metrics else 0,
                'total_requests_processed': sum(s.get('requests_processed', 0) for s in service_metrics),
            }
        except Exception as e:
            print(f"Warning: Could not compute summary stats: {e}")
        
        # Save results
        print(f"Saving to {config['output_file']}...", end=" ")
        with open(config['output_file'], 'w') as f:
            json.dump(output, f, indent=2)
        print(f"OK")
        
        # Print summary
        print(f"\nSummary:")
        print(f"  Timesteps: {sim.schedule.steps}")
        print(f"  Edge Servers: {output['component_counts']['edge_servers']}")
        print(f"  Faulty: {metrics_data['faulty_count']}")
        print(f"  Normal: {metrics_data['normal_count']}")
        print(f"  Execution Time: {elapsed_time:.3f}s")
        
        return output
    
    except Exception as e:
        print(f"\nX Error in scenario {scenario_name}:")
        print(f"  {e}")
        traceback.print_exc()
        return None

def main():
    """Run all configured scenarios."""
    print("\n" + "="*70)
    print("BYZANTINE FAULT SIMULATION TEST SUITE")
    print("="*70)
    
    results = {}
    
    for scenario in SCENARIOS_TO_RUN:
        if scenario not in SCENARIO_CONFIGS:
            print(f"\nSkipping unknown scenario: {scenario}")
            continue
        
        result = run_scenario(scenario)
        if result:
            results[scenario] = result
    
    # Generate comparison summary
    if results:
        print(f"\n{'='*70}")
        print("COMPARISON SUMMARY")
        print(f"{'='*70}")
        print(f"{'Scenario':<30} {'Faulty':<8} {'Normal':<8} {'Time (s)':<12}")
        print("-" * 70)
        
        for scenario, result in results.items():
            counts = result['component_counts']
            exec_time = result['simulation_stats']['real_world_seconds']
            print(f"{scenario:<30} {counts['faulty_servers']:<8} "
                  f"{counts['normal_servers']:<8} {exec_time:<12.3f}")
    
    # Save combined results
    print(f"\nSaving combined results...", end=" ")
    summary = {
        "test_suite": "Byzantine Fault Simulation",
        "scenarios_executed": len(results),
        "scenarios": results,
    }
    
    with open("test_suite_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("OK")
    
    print(f"\n{'='*70}")
    print("TEST SUITE COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
