"""
CORRECTED: Dataset Generation Template
File: dataset_corrected_template.py

This version addresses all issues found in the comprehensive analysis:
1. Correct return statement
2. Proper component naming
3. No redundant relationship definitions
4. Request handling at runtime, not in dataset
5. Fault_type properly exposed
"""

import random
import math
from typing import Dict, List, Tuple

# Use the corrected mobility function
from v2_mobility import random_waypoint_mobility

SIMULATION_CONFIG = {
    "bounds": (0, 0, 10000, 10000),  # (x_min, y_min, x_max, y_max)
    "timesteps": 500,
    "mobility_model": "random_waypoint_mobility",
    "update_frequency": 1,  # Update every timestep
    "boundary_handling": "bounce",  # bounce, wrap, or stop
}


def calculate_user_mobility_pattern(trace: List[List[float]]) -> Dict:
    """Calculate mobility statistics from coordinate trace."""
    if len(trace) < 2:
        return {
            "total_distance": 0,
            "displacement": 0,
            "efficiency": 0,
            "avg_speed": 0,
            "trace_length": 0,
        }
    
    # Calculate total distance
    total_distance = sum(
        math.hypot(trace[i+1][0] - trace[i][0], 
                  trace[i+1][1] - trace[i][1])
        for i in range(len(trace) - 1)
    )
    
    # Calculate displacement (straight line distance)
    displacement = math.hypot(
        trace[-1][0] - trace[0][0],
        trace[-1][1] - trace[0][1]
    )
    
    # Path efficiency (how direct the path was)
    efficiency = (displacement / total_distance) if total_distance > 0 else 0
    
    # Average speed
    avg_speed = total_distance / len(trace) if len(trace) > 0 else 0
    
    return {
        "total_distance": total_distance,
        "displacement": displacement,
        "efficiency": efficiency,
        "avg_speed": avg_speed,
        "trace_length": len(trace),
    }


def get_nearby_servers(user_coords: List[float], edge_servers: List[Dict], 
                      range_distance: float) -> List[Dict]:
    """Find edge servers within communication range of a user."""
    nearby = []
    
    for server in edge_servers:
        server_coords = server["attributes"]["coordinates"]
        distance = math.hypot(
            server_coords[0] - user_coords[0],
            server_coords[1] - user_coords[1]
        )
        
        if distance <= range_distance:
            nearby.append({
                'server_id': server['attributes']['id'],
                'server_name': server['attributes']['name'],
                'distance': distance,
                'latency_ms': distance / 100 + server['attributes'].get('base_latency', 5)
            })
    
    return sorted(nearby, key=lambda x: x['distance'])


def generate_base_stations(num_edge_servers: int = 500) -> List[Dict]:
    """Generate base stations for wireless connectivity."""
    base_stations = []
    bs_count = max(1, num_edge_servers // 50)
    
    x_min, y_min, x_max, y_max = SIMULATION_CONFIG["bounds"]
    
    for bs_id in range(1, bs_count + 1):
        base_stations.append({
            "attributes": {
                "id": bs_id,
                "name": f"base_station_{bs_id}",
                "coordinates": [random.uniform(x_min, x_max), random.uniform(y_min, y_max)],
                "wireless_latency": random.uniform(2, 10),
                "coverage_radius": 5000,
            },
            "relationships": {}  # No direct EdgeServer link needed
        })
    
    return base_stations


def generate_network_switches() -> List[Dict]:
    """Generate core network switches."""
    x_min, y_min, x_max, y_max = SIMULATION_CONFIG["bounds"]
    center_x, center_y = (x_max - x_min) / 2, (y_max - y_min) / 2
    
    switches = []
    for sw_id in range(1, 3):
        switches.append({
            "attributes": {
                "id": sw_id,
                "name": f"network_switch_{sw_id}",
                "coordinates": [center_x + random.uniform(-1000, 1000), center_y + random.uniform(-1000, 1000)],
                "switch_latency": random.uniform(0.1, 1.0),
                "number_of_ports": random.randint(32, 128),
            },
            "relationships": {}
        })
    
    return switches


def generate_edge_servers(num_servers: int = 500, 
                         malicious_percentage: float = 0.0) -> List[Dict]:
    """Generate edge servers with optional fault injection."""
    servers = []
    
    # Define server tiers with different capabilities
    server_tiers = [
        {"name": "tier_1_high_end", "cpu": 64000, "memory": 256000, "disk": 2000000, "latency_base": 2},
        {"name": "tier_2_mid_range", "cpu": 32000, "memory": 128000, "disk": 1000000, "latency_base": 5},
        {"name": "tier_3_standard", "cpu": 16000, "memory": 64000, "disk": 500000, "latency_base": 8},
        {"name": "tier_4_lightweight", "cpu": 8000, "memory": 32000, "disk": 250000, "latency_base": 10},
        {"name": "tier_5_minimal", "cpu": 4000, "memory": 16000, "disk": 125000, "latency_base": 15},
    ]
    
    # Optionally select which servers will be faulty
    num_faulty = int(num_servers * malicious_percentage / 100.0)
    faulty_indices = set(random.sample(range(num_servers), num_faulty)) if num_faulty > 0 else set()
    
    x_min, y_min, x_max, y_max = SIMULATION_CONFIG["bounds"]
    
    for i in range(1, num_servers + 1):
        tier = server_tiers[(i - 1) % len(server_tiers)]
        
        server_attrs = {
            "id": i,
            "name": f"edge_server_{i}",
            "tier": tier["name"],
            "cpu": tier["cpu"],
            "memory": tier["memory"],
            "disk": tier["disk"],
            "coordinates": [
                random.uniform(x_min, x_max),
                random.uniform(y_min, y_max)
            ],
            "base_latency": tier["latency_base"],
            "active": True,
        }
        
        # Mark as faulty if needed (dataset-level marker)
        if (i - 1) in faulty_indices:
            # NOTE: Fault type will be set during dataset creation
            # based on the specific scenario
            server_attrs["is_marked_faulty"] = True
        
        servers.append({
            "attributes": server_attrs,
            "relationships": {}  # No relationships defined at creation time
        })
    
    return servers


def generate_users(num_users: int = 5000, num_apps: int = 2000) -> List[Dict]:
    """Generate mobile users with application access patterns."""
    users = []
    user_types = ["premium", "standard", "basic", "corporate", "research"]
    
    x_min, y_min, x_max, y_max = SIMULATION_CONFIG["bounds"]
    
    for u in range(1, num_users + 1):
        user_type = user_types[(u - 1) % len(user_types)]
        
        if user_type == "premium":
            speed = random.uniform(5, 20)
            num_user_apps = random.randint(3, 8)
        elif user_type == "corporate":
            speed = random.uniform(2, 8)
            num_user_apps = random.randint(2, 5)
        elif user_type == "research":
            speed = random.uniform(3, 10)
            num_user_apps = random.randint(2, 6)
        else:
            speed = random.uniform(1, 5)
            num_user_apps = random.randint(1, 4)
        
        user_app_ids = random.sample(range(1, num_apps + 1), min(num_user_apps, num_apps))
        # Note: User-Application relationships will be established during simulation
        # Not defining them upfront to avoid initialization issues
        
        users.append({
            "attributes": {
                "id": u,
                "name": f"user_{u}",
                "type": user_type,
                "coordinates": [random.uniform(x_min, x_max), random.uniform(y_min, y_max)],
                "mobility_speed": speed,
                "request_rate": random.uniform(0.1, 5.0),
                "active": True,
            },
            "relationships": {
                "mobility_model": "random_waypoint_mobility",
            }
        })
    
    return users


def generate_applications(num_apps: int = 2000, num_services: int = 4000) -> List[Dict]:
    """Generate applications with service composition."""
    applications = []
    
    app_categories = [
        "video_streaming", "iot_analytics", "ar_vr", "healthcare_monitoring",
        "autonomous_vehicle", "smart_city", "gaming", "industrial_iot",
        "ml_inference", "real_time_processing", "batch_processing", "database",
        "iot_monitoring", "edge_ai", "autonomous_robot", "immersive_media"
    ]
    
    for a in range(1, num_apps + 1):
        category = app_categories[(a - 1) % len(app_categories)]
        
        if category == "video_streaming":
            cpu = random.randint(200, 500)
            memory = random.randint(256, 1024)
            deadline = random.randint(500, 2000)
            num_app_services = random.randint(2, 4)
        elif category == "ar_vr":
            cpu = random.randint(300, 600)
            memory = random.randint(512, 2048)
            deadline = random.randint(100, 300)
            num_app_services = random.randint(3, 5)
        elif category == "autonomous_vehicle":
            cpu = random.randint(400, 800)
            memory = random.randint(1024, 4096)
            deadline = random.randint(50, 150)
            num_app_services = random.randint(3, 5)
        elif category == "healthcare_monitoring":
            cpu = random.randint(100, 300)
            memory = random.randint(128, 512)
            deadline = random.randint(1000, 5000)
            num_app_services = random.randint(2, 3)
        elif category == "ml_inference":
            cpu = random.randint(500, 1000)
            memory = random.randint(2048, 8192)
            deadline = random.randint(200, 1000)
            num_app_services = random.randint(3, 4)
        else:
            cpu = random.randint(150, 400)
            memory = random.randint(256, 1024)
            deadline = random.randint(500, 3000)
            num_app_services = random.randint(2, 3)
        
        app_service_ids = random.sample(range(1, num_services + 1), min(num_app_services, num_services))
        # Note: Application-Service relationships will be established during simulation
        # Not defining them upfront to avoid initialization issues
        
        applications.append({
            "attributes": {
                "id": a,
                "name": f"{category}_{a}",
                "category": category,
                "cpu_demand": cpu,
                "memory_demand": memory,
                "deadline": deadline,
                "priority": random.randint(1, 10),
            },
            "relationships": {}
        })
    
    return applications


def generate_images(num_services: int = 4000) -> List[Dict]:
    """Generate container images for services."""
    images = []
    
    # Create one image per service
    for i in range(1, num_services + 1):
        image_digest = f"sha256:{i:064d}"
        images.append({
            "attributes": {
                "id": i,
                "name": f"image_{i}",
                "digest": image_digest,
                "tag": "1.0.0",
                "architecture": "amd64",
                "layers": [
                    f"sha256:layer1_{i:060d}",
                    f"sha256:layer2_{i:060d}",  
                    f"sha256:layer3_{i:060d}",
                ],
            },
            "relationships": {}
        })
    
    return images


def generate_services(num_services: int = 4000) -> List[Dict]:
    """Generate containerized services with container image metadata."""
    services = []
    
    for s in range(1, num_services + 1):
        # Create image digest for lookup during provisioning
        image_digest = f"sha256:{s:064d}"
        
        services.append({
            "attributes": {
                "id": s,
                "name": f"service_{s}",
                "image_digest": image_digest,  # IMPORTANT: Used for lookup during provision()
                "cpu_demand": random.randint(500, 2000),
                "memory_demand": random.randint(1000, 4000),
                "processing_time_ms": random.randint(100, 1000),
                "dependency_chain": random.randint(1, 3),
            },
            "relationships": {
                "image": {"class": "ContainerImage", "id": s}  # Link to corresponding image
            }
        })
    
    return services


def generate_service_requests(applications: List[Dict], users: List[Dict], 
                             num_requests: int = 10000) -> List[Dict]:
    """Generate service requests as list of dictionaries."""
    requests = []
    
    for req_id in range(1, num_requests + 1):
        user = random.choice(users)
        app = random.choice(applications)
        
        # Variation in resource demands
        cpu_var = random.uniform(0.8, 1.2)
        memory_var = random.uniform(0.8, 1.2)
        
        request_obj = {
            "id": req_id,
            "cpu_demand": int(app["attributes"]["cpu_demand"] * cpu_var),
            "memory_demand": int(app["attributes"]["memory_demand"] * memory_var),
            "deadline": app["attributes"]["deadline"],
            "priority": app["attributes"]["priority"],
            "arrival_time": random.uniform(0, 100000),
            "expected_execution_time": random.randint(100, 2000),
            "user_id": user["attributes"]["id"],
            "application_id": app["attributes"]["id"],
        }
        
        requests.append(request_obj)
    
    return requests


def generate_container_layers(num_services: int = 4000) -> List[Dict]:
    """Generate container layers from all service images."""
    layers = []
    layer_id = 1
    
    # Create 3 layers for each service image
    for i in range(1, num_services + 1):
        for layer_idx in range(1, 4):
            layer_digest = f"sha256:layer{layer_idx}_{i:060d}"
            layers.append({
                "attributes": {
                    "id": layer_id,
                    "digest": layer_digest,
                    "size": random.randint(50, 500),  # MB
                    "instruction": f"ADD /layer{layer_idx}",
                },
                "relationships": {}
            })
            layer_id += 1
    
    return layers


def generate_registries(num_edge_servers: int = 500, num_services: int = 4000) -> Tuple[List[Dict], List[Dict]]:
    """Generate container registries and their layers.
    
    Returns:
        (registries, container_layers)
    """
    # Generate all container layers
    container_layers = generate_container_layers(num_services)
    
    # Create registries on a subset of edge servers (at least 1, max 10% of servers)
    registries = []
    num_registries = max(1, min(num_edge_servers // 10, 50))
    registry_servers = list(range(1, num_registries + 1))
    
    for r_idx, server_id in enumerate(registry_servers, 1):
        registries.append({
            "attributes": {
                "id": r_idx,
                "name": f"registry_{r_idx}",
                "cpu_demand": 1000,
                "memory_demand": 5000,
            },
            "relationships": {
                "server": {"class": "EdgeServer", "id": server_id},
            }
        })
    
    return registries, container_layers


def create_dataset(
    num_edge_servers: int = 500,
    num_users: int = 5000,
    num_applications: int = 2000,
    num_services: int = 4000,
    num_requests: int = 10000,
    simulation_timesteps: int = 500,
    malicious_percentage: float = 0.0,
    fault_type: str = None,
    seed: int = 42
) -> tuple:
    """
    Create a complete EdgeSimPy dataset.
    
    Args:
        num_edge_servers: Number of edge servers to generate
        num_users: Number of mobile users
        num_applications: Number of applications
        num_services: Number of services
        num_requests: Number of service requests
        simulation_timesteps: Expected simulation length
        malicious_percentage: Percentage of servers to mark as faulty
        fault_type: Type of fault to inject ('processing_delay_attack', 
                   'request_dropping', 'false_resource_reporting', 
                   'selective_service_rejection', or None)
        seed: Random seed for reproducibility
    
    Returns:
        tuple: (dataset, SERVICE_REQUESTS, DATASET_METADATA)
    """
    random.seed(seed)
    
    # Generate components
    edge_servers = generate_edge_servers(num_edge_servers, malicious_percentage)
    base_stations = generate_base_stations(num_edge_servers)
    network_switches = generate_network_switches()
    users = generate_users(num_users, num_applications)
    applications = generate_applications(num_applications, num_services)
    images = generate_images(num_services)  # Must generate before services!
    services = generate_services(num_services)
    registries, container_layers = generate_registries(num_edge_servers, num_services)
    requests = generate_service_requests(applications, users, num_requests)
    
    # Add layer relationships to registry servers so layers can be accessed
    # This ensures EdgeServer.step() finds layers in registry.server.container_layers
    if registries and container_layers:
        for registry in registries:
            # Add all layers as relationships to the registry's server
            server_id = registry["relationships"]["server"]["id"]
            for layer_idx, layer in enumerate(container_layers, 1):
                registry["relationships"][f"layer_{layer_idx}"] = {
                    "class": "ContainerLayer",
                    "id": layer_idx
                }
            
            # Also add layers to the registry server's own relationships
            # This helps EdgeSimPy populate the server's container_layers list
            if server_id <= len(edge_servers):
                server = edge_servers[server_id - 1]
                if "relationships" not in server:
                    server["relationships"] = {}
                
                for layer_idx, layer in enumerate(container_layers, 1):
                    server["relationships"][f"preload_layer_{layer_idx}"] = {
                        "class": "ContainerLayer",
                        "id": layer_idx
                    }
    
    # Set fault type on marked faulty servers
    if fault_type and malicious_percentage > 0:
        for server in edge_servers:
            if server["attributes"].get("is_marked_faulty"):
                server["attributes"]["fault_type"] = fault_type
                # Store fault configuration (can be customized per fault type)
                server["attributes"]["fault_config"] = {
                    "slowdown_factor": 2.0,  # For processing_delay_attack
                    "drop_probability": 0.3,  # For request_dropping
                    "lie_probability": 0.25,  # For false_resource_reporting
                    "inflation_factor": 1.5,  # For false_resource_reporting
                    "rejection_config": {  # For selective_service_rejection
                        "target_application_ids": list(range(1, min(51, num_applications))),  # Target first 50 apps
                        "rejection_rate": 0.8,
                    }
                }
                del server["attributes"]["is_marked_faulty"]  # Clean up marker
    
    # Build dataset with proper component class names
    dataset = {
        "EdgeServer": edge_servers,
        "BaseStation": base_stations,
        "NetworkSwitch": network_switches,
        "User": users,
        "Application": applications,
        "ContainerImage": images,  # Correct EdgeSimPy component name
        "ContainerLayer": container_layers,
        "ContainerRegistry": registries,
        "Service": services,
    }
    
    # Metadata about the dataset
    DATASET_METADATA = {
        "num_edge_servers": num_edge_servers,
        "num_users": num_users,
        "num_applications": num_applications,
        "num_services": num_services,
        "num_requests": num_requests,
        "simulation_timesteps": simulation_timesteps,
        "simulation_bounds": SIMULATION_CONFIG["bounds"],
        "malicious_percentage": malicious_percentage,
        "fault_type": fault_type,
        "seed": seed,
        "scale": "large",
    }
    
    # CORRECT: Return all three values
    return dataset, requests, DATASET_METADATA


# Export the mobility model function for simulator registration
USER_DEFINED_FUNCTIONS = [random_waypoint_mobility]
