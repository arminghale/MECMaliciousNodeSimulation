import random
import math
from typing import Dict, List, Tuple

SIMULATION_CONFIG = {
    "bounds": (0, 0, 10000, 10000),  # (x_min, y_min, x_max, y_max)
    "timesteps": 500,
    "mobility_model": "random_waypoint",
    "update_frequency": 1,  # Update every timestep
}

def random_waypoint(user: Dict, bounds: Tuple = (0, 0, 10000, 10000), 
                    boundary_handling: str = "bounce") -> None:
    try:
        # Get current coordinates
        coords = None
        if hasattr(user, 'attributes') and isinstance(user.attributes, dict):
            coords = user.attributes.get('coordinates')
        if coords is None and hasattr(user, 'coordinates'):
            coords = user.coordinates
        if isinstance(user, dict):
            coords = user.get('coordinates')
        
        if coords is None:
            return
        
        coords = list(coords)  # Ensure it's mutable
        
        # Random direction (uniform angle distribution)
        angle = random.uniform(0, 2 * math.pi)
        dx = math.cos(angle)
        dy = math.sin(angle)
        
        # Get mobility speed
        speed = 1
        if isinstance(user, dict):
            speed = user.get('mobility_speed', 1)
        elif hasattr(user, 'attributes') and isinstance(user.attributes, dict):
            speed = user.attributes.get('mobility_speed', speed)
        else:
            speed = getattr(user, 'mobility_speed', speed)
        
        # Calculate new position
        new_x = coords[0] + dx * speed
        new_y = coords[1] + dy * speed
        
        x_min, y_min, x_max, y_max = bounds
        
        # Apply boundary handling
        if boundary_handling == "bounce":
            if new_x < x_min or new_x > x_max:
                dx = -dx
                new_x = coords[0] + dx * speed
            if new_y < y_min or new_y > y_max:
                dy = -dy
                new_y = coords[1] + dy * speed
        
        elif boundary_handling == "wrap":
            new_x = x_min + (new_x - x_min) % (x_max - x_min)
            new_y = y_min + (new_y - y_min) % (y_max - y_min)
        
        elif boundary_handling == "stop":
            new_x = max(x_min, min(x_max, new_x))
            new_y = max(y_min, min(y_max, new_y))
        
        coords[0] = new_x
        coords[1] = new_y
        
        # Update user coordinates
        if isinstance(user, dict):
            user['coordinates'] = coords
        else:
            if hasattr(user, 'attributes') and isinstance(user.attributes, dict):
                user.attributes['coordinates'] = coords
            if hasattr(user, 'coordinates'):
                user.coordinates = coords
        
        # Record trace
        try:
            if isinstance(user, dict) and 'coordinates_trace' in user:
                user['coordinates_trace'].append(list(coords))
            elif hasattr(user, 'coordinates_trace'):
                user.coordinates_trace.append(list(coords))
        except Exception:
            pass
            
    except Exception as e:
        pass

def calculate_user_mobility_pattern(user: Dict, timesteps: int) -> Dict:
    trace = user.get('coordinates_trace', [])
    
    if len(trace) < 2:
        return {
            "total_distance": 0,
            "displacement": 0,
            "efficiency": 0,
            "avg_speed": 0
        }
    
    # Calculate total distance
    total_distance = sum(
        math.hypot(trace[i+1][0] - trace[i][0], 
                  trace[i+1][1] - trace[i][1])
        for i in range(len(trace) - 1)
    )
    
    # Calculate displacement
    displacement = math.hypot(
        trace[-1][0] - trace[0][0],
        trace[-1][1] - trace[0][1]
    )
    
    # Path efficiency
    efficiency = (displacement / total_distance) if total_distance > 0 else 0
    
    # Average speed
    avg_speed = total_distance / len(trace) if len(trace) > 0 else 0
    
    return {
        "total_distance": total_distance,
        "displacement": displacement,
        "efficiency": efficiency,
        "avg_speed": avg_speed,
        "trace_length": len(trace)
    }

def get_nearby_servers(user: Dict, edge_servers: List[Dict], 
                      range_distance: float) -> List[Dict]:
    user_coords = user.get('coordinates', [0, 0])
    nearby = []
    
    for server in edge_servers:
        server_coords = server.get('coordinates', [0, 0])
        distance = math.hypot(
            server_coords[0] - user_coords[0],
            server_coords[1] - user_coords[1]
        )
        
        if distance <= range_distance:
            nearby.append({
                'server_id': server['id'],
                'server_name': server.get('name', f"server_{server['id']}"),
                'distance': distance,
                'latency_ms': distance / 100 + server.get('base_latency', 5)
            })
    
    return sorted(nearby, key=lambda x: x['distance'])


def generate_edge_servers(num_servers: int = 500, malicious_percentage: float = 20.0) -> List[Dict]:
    servers = []
    server_tiers = [
        {"name": "tier_1_high_end", "cpu": 64000, "memory": 256000, "disk": 2000000, "latency_base": 2},
        {"name": "tier_2_mid_range", "cpu": 32000, "memory": 128000, "disk": 1000000, "latency_base": 5},
        {"name": "tier_3_standard", "cpu": 16000, "memory": 64000, "disk": 500000, "latency_base": 8},
        {"name": "tier_4_lightweight", "cpu": 8000, "memory": 32000, "disk": 250000, "latency_base": 10},
        {"name": "tier_5_minimal", "cpu": 4000, "memory": 16000, "disk": 125000, "latency_base": 15},
    ]
    
    fault_types = [
        "processing_delay_attack",
        "request_dropping",
        "false_resource_reporting",
        "selective_service_rejection"
    ]
    
    # Calculate number of malicious servers
    num_malicious = int(num_servers * malicious_percentage / 100.0)
    
    # Randomly select which server indices will be malicious
    malicious_indices = set(random.sample(range(num_servers), num_malicious))
    
    x_min, y_min, x_max, y_max = SIMULATION_CONFIG["bounds"]
    
    for i in range(1, num_servers + 1):
        tier = server_tiers[i % len(server_tiers)]
        is_malicious = (i - 1) in malicious_indices  # i is 1-indexed
        
        # If malicious, randomly select a fault type
        fault_type = None
        if is_malicious:
            fault_type = random.choice(fault_types)
        
        servers.append({
            "attributes": {
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
                "load": 0,
                "power_consumption": 0,
                "active": True,
                "fault_type": fault_type,
            },
            "relationships": {}
        })
    
    return servers


def generate_users(num_users: int = 5000) -> List[Dict]:
    users = []
    user_types = ["premium", "standard", "basic", "corporate", "research"]
    
    x_min, y_min, x_max, y_max = SIMULATION_CONFIG["bounds"]
    
    for u in range(1, num_users + 1):
        user_type = user_types[u % len(user_types)]
        
        # Different mobility characteristics by user type
        if user_type == "premium":
            speed = random.uniform(5, 20)  # Fast-moving premium users
            num_apps = random.randint(20, 40)
        elif user_type == "corporate":
            speed = random.uniform(2, 8)   # Moderate corporate users
            num_apps = random.randint(15, 30)
        elif user_type == "research":
            speed = random.uniform(3, 10)  # Research users
            num_apps = random.randint(10, 25)
        else:
            speed = random.uniform(1, 5)   # Slower standard/basic users
            num_apps = random.randint(5, 15)
        
        users.append({
            "attributes": {
                "id": u,
                "name": f"user_{u}",
                "type": user_type,
                "coordinates": [
                    random.uniform(x_min, x_max),
                    random.uniform(y_min, y_max)
                ],
                "mobility_speed": speed,
                "mobility_model": "random_waypoint",
                "coordinates_trace": [],
                "request_rate": random.uniform(0.1, 5.0),
                "active": True,
                "connection_history": [],
            },
            "relationships": {"mobility_model": "random_waypoint"}
        })
    
    return users


def generate_applications(num_apps: int = 2000) -> List[Dict]:
    applications = []
    app_categories = [
        "video_streaming", "iot_analytics", "ar_vr", "healthcare_monitoring",
        "autonomous_vehicle", "smart_city", "gaming", "industrial_iot",
        "ml_inference", "real_time_processing", "batch_processing", "database",
        "iot_monitoring", "edge_ai", "autonomous_robot", "immersive_media"
    ]
    
    for a in range(1, num_apps + 1):
        category = app_categories[a % len(app_categories)]
        
        # Category-specific requirements
        if category == "video_streaming":
            cpu = random.randint(200, 500)
            memory = random.randint(256, 1024)
            deadline = random.randint(500, 2000)
        elif category == "ar_vr":
            cpu = random.randint(300, 600)
            memory = random.randint(512, 2048)
            deadline = random.randint(100, 300)
        elif category == "autonomous_vehicle":
            cpu = random.randint(400, 800)
            memory = random.randint(1024, 4096)
            deadline = random.randint(50, 150)
        elif category == "healthcare_monitoring":
            cpu = random.randint(100, 300)
            memory = random.randint(128, 512)
            deadline = random.randint(1000, 5000)
        elif category == "ml_inference":
            cpu = random.randint(500, 1000)
            memory = random.randint(2048, 8192)
            deadline = random.randint(200, 1000)
        else:
            cpu = random.randint(150, 400)
            memory = random.randint(256, 1024)
            deadline = random.randint(500, 3000)
        
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


def generate_services(num_services: int = 4000) -> List[Dict]:
    services = []
    
    for s in range(1, num_services + 1):
        services.append({
            "attributes": {
                "id": s,
                "name": f"service_{s}",
                "cpu_demand": random.randint(500, 2000),
                "memory_demand": random.randint(1000, 4000),
                "processing_time_ms": random.randint(100, 1000),
                "dependency_chain": random.randint(1, 3),
                "load": 0,
                "power_consumption": 0,
            },
            "relationships": {}
        })
    
    return services


def generate_service_requests(applications: List[Dict], users: List[Dict], 
                             num_requests: int = 10000) -> List[Dict]:
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
        }
        
        requests.append({
            "attributes": request_obj,
            "relationships": {}
        })
    
    return requests


def create_dataset(
    num_edge_servers: int = 500,
    num_users: int = 5000,
    num_applications: int = 2000,
    num_services: int = 4000,
    num_requests: int = 10000,
    simulation_timesteps: int = 500,
    seed: int = 42,
    malicious_percentage: float = 20.0
) -> Dict:
    random.seed(seed)
    
    edge_servers = generate_edge_servers(num_edge_servers, malicious_percentage)
    
    users = generate_users(num_users)
    
    applications = generate_applications(num_applications)
    
    services = generate_services(num_services)
    
    requests = generate_service_requests(applications, users, num_requests)
    
    # **BUILD RELATIONSHIPS BETWEEN COMPONENTS**
    
    # 1. Deploy services to edge servers (round-robin distribution)
    services_per_server = len(services) // len(edge_servers)
    for srv_idx, service in enumerate(services):
        # Assign service to an edge server
        server_idx = srv_idx % len(edge_servers)
        target_server = edge_servers[server_idx]
        
        # Service → EdgeServer relationship
        service["relationships"]["server"] = {
            "class": "EdgeServer",
            "id": target_server["attributes"]["id"]
        }
        
        # Add this service to the server's service list
        if "services" not in edge_servers[server_idx]["relationships"]:
            edge_servers[server_idx]["relationships"]["services"] = []
        
        edge_servers[server_idx]["relationships"]["services"].append({
            "class": "Service",
            "id": service["attributes"]["id"]
        })
    
    # 2. User→Application relationships are intentionally omitted.
    # The `User` component initializes and manages its own access patterns
    # internally; assigning application relationships from the dataset
    # can desynchronize the internal `access_patterns` state and cause
    # KeyError during `User.collect()`.
    
    # 3. Link applications to services (each app uses multiple services)
    for app in applications:
        num_services_for_app = random.randint(2, 8)
        app_services = random.sample(range(len(services)), min(num_services_for_app, len(services)))
        
        app["relationships"]["services"] = [
            {"class": "Service", "id": services[svc_idx]["attributes"]["id"]}
            for svc_idx in app_services
        ]
    
    # 4. Group requests by service and add to relationships (as before)
    requests_per_service = len(requests) // len(services)
    for idx, service in enumerate(services):
        start_idx = idx * requests_per_service
        end_idx = start_idx + requests_per_service if idx < len(services) - 1 else len(requests)
        service_requests = requests[start_idx:end_idx]
        
        service["relationships"]["pending_requests"] = [
            {"class": "Service", "id": service["attributes"]["id"], "request_id": r["attributes"]["id"]}
            for r in service_requests
        ]
    
    # Build dataset with only component class names
    dataset = {
        "EdgeServer": edge_servers,
        "User": users,
        "Application": applications,
        "Service": services,
    }

    # Keep requests and metadata available at module level for direct access
    SERVICE_REQUESTS = requests
    DATASET_METADATA = {
        "num_edge_servers": num_edge_servers,
        "num_users": num_users,
        "num_applications": num_applications,
        "num_services": num_services,
        "num_requests": num_requests,
        "simulation_timesteps": simulation_timesteps,
        "simulation_bounds": SIMULATION_CONFIG["bounds"],
        "seed": seed,
        "scale": "large",
        "malicious_percentage": malicious_percentage,
        "fault_type": "mixed_Byzantine",
    }

    return dataset, SERVICE_REQUESTS, DATASET_METADATA


DATASET, SERVICE_REQUESTS, DATASET_METADATA = create_dataset(
    num_edge_servers=500,
    num_users=5000,
    num_applications=2000,
    num_services=4000,
    num_requests=10000,
    simulation_timesteps=500,
    seed=42,
    malicious_percentage=20.0
)

# Export user-defined functions so callers (e.g., the test harness) can register them
# with the Simulator. This allows dataset relationships to reference these
# functions by name and have the simulator assign the callable to agents.
USER_DEFINED_FUNCTIONS = [random_waypoint]
