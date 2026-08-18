import os
import sys
import argparse
import random
import msgpack
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")                               # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from edge_sim_py import *  # noqa: F403, F401
from edge_sim_py.components.edge_server import EdgeServer as _EdgeServer


class FaultyEdgeServer(_EdgeServer):

    PROCESSING_DELAY_ATTACK    = "processing_delay_attack"
    REQUEST_DROPPING           = "request_dropping"
    FALSE_RESOURCE_REPORTING   = "false_resource_reporting"
    SELECTIVE_SERVICE_REJECTION = "selective_service_rejection"
    MIXED                      = "mixed"

    def _init_fault(self, fault_type=None, fault_config=None):
        self.fault_type = fault_type
        self.fault_config = fault_config or {}
        # fault counters
        self.delayed_requests = 0
        self.dropped_requests = 0
        self.rejected_requests = 0
        self.false_reports_count = 0
        # request counters
        self.requests_received = 0
        self.requests_processed = 0
        self.requests_failed = 0
        self._req_tick = 0
        # deadline tracking
        self.deadline_violations = 0
        self.total_processing_time = 0  # cumulative latency
        # false reporting tracking
        self.reported_cpu_demand = 0
        self.reported_memory_demand = 0

    def __init__(self, *args, fault_type=None, fault_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_fault(fault_type, fault_config)

    def _fault_active(self, *types):
        return self.fault_type in types or self.fault_type == self.MIXED

    def step(self):
        self._process_requests()
        self._apply_false_resource_tick()
        super().step()

    def _process_requests(self):
        if not getattr(self, "services", None):
            return
        self._req_tick += 1
        if self._req_tick % 5 != 0:          # throttle: batches every 5 ticks
            return

        cfg         = self.fault_config
        slowdown    = cfg.get("slowdown_factor", 3.0)  # default slowdown if not in config
        delay_prob  = cfg.get("delay_probability", 0.4)
        drop_prob   = cfg.get("drop_probability", 0.3)
        base_ms     = cfg.get("base_latency_ms", 10)
        deadline_sla = (DEADLINE_MIN + DEADLINE_MAX) / 2  # use midpoint of deadline range
        rej_cfg     = cfg.get("rejection_config", {})
        target_apps = rej_cfg.get("target_application_ids", [])
        rej_rate    = rej_cfg.get("rejection_rate", 0.8)

        for svc in self.services:
            if not getattr(svc, "_available", False):
                continue
            app_id = getattr(getattr(svc, "application", None), "id", None)

            for _ in range(3):                           # 3 requests per batch
                self.requests_received += 1
                fault_hit = False
                processing_time = base_ms  # Start with normal processing time

                # 1) Selective service rejection
                if (not fault_hit
                        and self._fault_active(self.SELECTIVE_SERVICE_REJECTION)
                        and app_id in target_apps
                        and random.random() < rej_rate):
                    self.rejected_requests += 1
                    self.requests_failed += 1
                    fault_hit = True

                # 2) Request dropping
                if (not fault_hit
                        and self._fault_active(self.REQUEST_DROPPING)
                        and random.random() < drop_prob):
                    self.dropped_requests += 1
                    self.requests_failed += 1
                    fault_hit = True

                # 3) Processing delay attack (request succeeds, but slow)
                if (not fault_hit
                        and self._fault_active(self.PROCESSING_DELAY_ATTACK)
                        and random.random() < delay_prob):
                    self.delayed_requests += 1
                    processing_time = base_ms * slowdown  # Inflated latency

                if not fault_hit:
                    self.requests_processed += 1
                    # Track processing time and check deadline violations
                    self.total_processing_time += processing_time
                    if processing_time > deadline_sla:
                        self.deadline_violations += 1

    def _apply_false_resource_tick(self):
        if not self._fault_active(self.FALSE_RESOURCE_REPORTING):
            # No false reporting, report actual values
            self.reported_cpu_demand = self.cpu_demand
            self.reported_memory_demand = self.memory_demand
            return
        
        lie_prob  = self.fault_config.get("lie_probability", 0.25)
        inflation = self.fault_config.get("inflation_factor", 1.5)
        
        if random.random() < lie_prob:
            # Report inflated resource usage (make server appear busier than it is)
            self.false_reports_count += 1
            self.reported_cpu_demand = min(self.cpu, self.cpu_demand * inflation)
            self.reported_memory_demand = min(self.memory, self.memory_demand * inflation)
        else:
            # Report truthfully this tick
            self.reported_cpu_demand = self.cpu_demand
            self.reported_memory_demand = self.memory_demand

    def collect(self):
        metrics = super().collect()
        if not isinstance(metrics, dict):
            metrics = {}
        
        # Calculate average processing time
        avg_processing_time = (self.total_processing_time / self.requests_processed 
                              if self.requests_processed > 0 else 0)
        
        metrics.update({
            "fault_type":             self.fault_type,
            "is_faulty":              True,
            "delayed_requests":       self.delayed_requests,
            "dropped_requests":       self.dropped_requests,
            "rejected_requests":      self.rejected_requests,
            "false_reports_count":    self.false_reports_count,
            "requests_received":      self.requests_received,
            "requests_processed":     self.requests_processed,
            "requests_failed":        self.requests_failed,
            "deadline_violations":    self.deadline_violations,
            "avg_processing_time":    avg_processing_time,
            "reported_cpu_demand":    self.reported_cpu_demand,
            "reported_memory_demand": self.reported_memory_demand,
            "total_faults_triggered": (
                self.delayed_requests + self.dropped_requests +
                self.rejected_requests + self.false_reports_count
            ),
        })
        return metrics


def convert_to_faulty(server, fault_type, fault_config):
    server.__class__ = FaultyEdgeServer
    server._init_fault(fault_type, fault_config)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Byzantine Fault Tolerance Simulation for Edge Computing")
    parser.add_argument("--servers", type=int, default=100, help="Total number of edge servers (default: 100)")
    parser.add_argument("--faulty", type=int, default=30, help="Percentage of faulty servers (default: 30)")
    
    # Randomized users per server
    parser.add_argument("--users-min", type=int, default=2, help="Minimum users per server (default: 2)")
    parser.add_argument("--users-max", type=int, default=4, help="Maximum users per server (default: 4)")
    
    # Randomized services per server
    parser.add_argument("--services-min", type=int, default=2, help="Minimum services per server (default: 2)")
    parser.add_argument("--services-max", type=int, default=4, help="Maximum services per server (default: 4)")
    
    parser.add_argument("--grid", type=int, default=2, help="Grid spacing for topology (default: 2)")
    parser.add_argument("--steps", type=int, default=100, help="Number of simulation steps (default: 100)")
    parser.add_argument("--dump", type=int, default=25, help="Dump interval for logs (default: 25)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (use -1 for random)")
    
    # Randomized deadline SLA
    parser.add_argument("--deadline-min", type=int, default=15, help="Minimum deadline SLA (default: 15)")
    parser.add_argument("--deadline-max", type=int, default=25, help="Maximum deadline SLA (default: 25)")
    
    # Randomized slowdown factor
    parser.add_argument("--slowdown-min", type=float, default=3.0, help="Minimum slowdown factor (default: 3.0)")
    parser.add_argument("--slowdown-max", type=float, default=5.0, help="Maximum slowdown factor (default: 5.0)")
    
    # Fault probability ranges
    parser.add_argument("--delay-prob-min", type=float, default=0.3, help="Minimum delay probability (default: 0.3)")
    parser.add_argument("--delay-prob-max", type=float, default=0.5, help="Maximum delay probability (default: 0.5)")
    
    parser.add_argument("--drop-prob-min", type=float, default=0.2, help="Minimum drop probability (default: 0.2)")
    parser.add_argument("--drop-prob-max", type=float, default=0.4, help="Maximum drop probability (default: 0.4)")
    
    parser.add_argument("--lie-prob-min", type=float, default=0.2, help="Minimum lie probability (default: 0.2)")
    parser.add_argument("--lie-prob-max", type=float, default=0.3, help="Maximum lie probability (default: 0.3)")
    
    parser.add_argument("--inflate-min", type=float, default=1.3, help="Minimum inflation factor (default: 1.3)")
    parser.add_argument("--inflate-max", type=float, default=1.7, help="Maximum inflation factor (default: 1.7)")
    
    parser.add_argument("--reject-rate-min", type=float, default=0.7, help="Minimum rejection rate (default: 0.7)")
    parser.add_argument("--reject-rate-max", type=float, default=0.9, help="Maximum rejection rate (default: 0.9)")
    
    return parser.parse_args()


# Parse command-line arguments
args = parse_arguments()

NUM_SERVERS       = args.servers
FAULTY_PERCENTAGE = args.faulty

# Ranges for randomization
USERS_MIN         = args.users_min
USERS_MAX         = args.users_max
SERVICES_MIN      = args.services_min
SERVICES_MAX      = args.services_max
DEADLINE_MIN      = args.deadline_min
DEADLINE_MAX      = args.deadline_max
SLOWDOWN_MIN      = args.slowdown_min
SLOWDOWN_MAX      = args.slowdown_max

# Fault parameter ranges
DELAY_PROB_MIN    = args.delay_prob_min
DELAY_PROB_MAX    = args.delay_prob_max
DROP_PROB_MIN     = args.drop_prob_min
DROP_PROB_MAX     = args.drop_prob_max
LIE_PROB_MIN      = args.lie_prob_min
LIE_PROB_MAX      = args.lie_prob_max
INFLATE_MIN       = args.inflate_min
INFLATE_MAX       = args.inflate_max
REJECT_RATE_MIN   = args.reject_rate_min
REJECT_RATE_MAX   = args.reject_rate_max

GRID_SPACING      = args.grid
NUM_STEPS         = args.steps
DUMP_INTERVAL     = args.dump
RANDOM_SEED       = None if args.seed == -1 else args.seed
LAYER_DIGEST      = "sha256:aabbccdd0001"
IMAGE_DIGEST      = "sha256:aabbccdd0002"

SERVER_CONFIGS    = {}

NUM_FAULTY = int(NUM_SERVERS * FAULTY_PERCENTAGE / 100)

if RANDOM_SEED is not None:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

# Fault types
FAULT_TYPES = [
    "processing_delay_attack",
    "request_dropping",
    "false_resource_reporting",
    "selective_service_rejection",
    "mixed",
]

# Fault configurations per type
def generate_fault_config(fault_type):
    """Generate randomized fault configuration for a specific fault type."""
    if fault_type == "processing_delay_attack":
        return {
            "slowdown_factor": random.uniform(SLOWDOWN_MIN, SLOWDOWN_MAX),
            "delay_probability": random.uniform(DELAY_PROB_MIN, DELAY_PROB_MAX),
            "base_latency_ms": 10,
        }
    elif fault_type == "request_dropping":
        return {
            "drop_probability": random.uniform(DROP_PROB_MIN, DROP_PROB_MAX),
        }
    elif fault_type == "false_resource_reporting":
        return {
            "lie_probability": random.uniform(LIE_PROB_MIN, LIE_PROB_MAX),
            "inflation_factor": random.uniform(INFLATE_MIN, INFLATE_MAX),
        }
    elif fault_type == "selective_service_rejection":
        return {
            "rejection_config": {
                "target_application_ids": [],  # dynamically set based on server
                "rejection_rate": random.uniform(REJECT_RATE_MIN, REJECT_RATE_MAX),
            },
        }
    elif fault_type == "mixed":
        return {
            "slowdown_factor": random.uniform(SLOWDOWN_MIN, SLOWDOWN_MAX),
            "delay_probability": random.uniform(DELAY_PROB_MIN * 0.75, DELAY_PROB_MAX * 0.75),  # slightly lower for mixed
            "base_latency_ms": 10,
            "drop_probability": random.uniform(DROP_PROB_MIN * 0.7, DROP_PROB_MAX * 0.7),  # slightly lower
            "lie_probability": random.uniform(LIE_PROB_MIN * 0.6, LIE_PROB_MAX * 0.6),  # slightly lower
            "inflation_factor": random.uniform(INFLATE_MIN * 0.9, INFLATE_MAX * 0.9),  # slightly lower
            "rejection_config": {
                "target_application_ids": [],  # dynamically set based on server
                "rejection_rate": random.uniform(REJECT_RATE_MIN * 0.75, REJECT_RATE_MAX * 0.75),  # slightly lower
            },
        }
    else:
        return {}


def _generate_server_defs():
    # Calculate grid dimensions
    grid_cols = int(np.ceil(np.sqrt(NUM_SERVERS)))
    grid_rows = int(np.ceil(NUM_SERVERS / grid_cols))
    
    server_defs = []
    for i in range(NUM_SERVERS):
        sid = i + 1
        row = i // grid_cols
        col = i % grid_cols
        coords = [col * GRID_SPACING, row * GRID_SPACING]
        
        # Randomize users and services per server
        num_users = random.randint(USERS_MIN, USERS_MAX)
        num_services = random.randint(SERVICES_MIN, SERVICES_MAX)
        SERVER_CONFIGS[sid] = {
            "users": num_users,
            "services": num_services,
        }
        
        server_defs.append({
            "id": sid,
            "coords": coords,
            "fault": None,
            "label": "HEALTHY",
        })
    
    # Randomly select faulty servers
    if NUM_FAULTY > 0:
        faulty_ids = set(random.sample(range(1, NUM_SERVERS + 1), NUM_FAULTY))
        
        # Assign fault types - ensure balanced distribution
        # If we have enough faulty servers, guarantee at least one of each type
        fault_assignments = []
        
        if NUM_FAULTY >= len(FAULT_TYPES):
            # Assign one of each fault type first
            fault_assignments = FAULT_TYPES.copy()
            # Fill remaining with random selections
            fault_assignments.extend([random.choice(FAULT_TYPES) for _ in range(NUM_FAULTY - len(FAULT_TYPES))])
            random.shuffle(fault_assignments)
        else:
            # Fewer faulty servers than fault types - just random selection
            fault_assignments = [random.choice(FAULT_TYPES) for _ in range(NUM_FAULTY)]
        
        for idx, sdef in enumerate(server_defs):
            if sdef["id"] in faulty_ids:
                fault_type = fault_assignments.pop(0)
                sdef["fault"] = fault_type
                sdef["label"] = fault_type.upper().replace("_", "-")
    
    return server_defs


def _generate_grid_links(server_defs):
    # Generate links for grid topology (4-connected: up, down, left, right)
    grid_cols = int(np.ceil(np.sqrt(NUM_SERVERS)))
    coord_to_id = {tuple(s["coords"]): s["id"] for s in server_defs}
    
    links = []
    for s in server_defs:
        sid = s["id"]
        x, y = s["coords"]
        # Right neighbor
        right = (x + GRID_SPACING, y)
        if right in coord_to_id:
            rid = coord_to_id[right]
            if (sid, rid) not in links and (rid, sid) not in links:
                links.append((sid, rid))
        # Down neighbor
        down = (x, y + GRID_SPACING)
        if down in coord_to_id:
            did = coord_to_id[down]
            if (sid, did) not in links and (did, sid) not in links:
                links.append((sid, did))
    
    return links


# Generate dynamic topology
SERVER_DEFS = _generate_server_defs()
LINK_PAIRS = _generate_grid_links(SERVER_DEFS)


def _build_dataset():
    ds = {}
    n_srv = len(SERVER_DEFS)

    # coordinate traces (static – no mobility)
    traces = {tuple(s["coords"]): [list(s["coords"])] * NUM_STEPS
              for s in SERVER_DEFS}

    ds["NetworkSwitch"] = []
    for s in SERVER_DEFS:
        sid = s["id"]
        link_ids = [i + 1 for i, (a, b) in enumerate(LINK_PAIRS)
                    if a == sid or b == sid]
        ds["NetworkSwitch"].append({
            "attributes": {
                "id": sid, "coordinates": s["coords"], "active": True,
                "power_model_parameters": {
                    "chassis_power": 60,
                    "ports_power_consumption": {"125": 1, "12.5": 0.3},
                },
            },
            "relationships": {
                "power_model": "ConteratoNetworkPowerModel",
                "edge_servers": [{"class": "EdgeServer", "id": sid}],
                "links": [{"class": "NetworkLink", "id": lid} for lid in link_ids],
                "base_station": {"class": "BaseStation", "id": sid},
            },
        })

    ds["NetworkLink"] = []
    for idx, (a, b) in enumerate(LINK_PAIRS, start=1):
        ds["NetworkLink"].append({
            "attributes": {
                "id": idx, "delay": 5, "bandwidth": 12.5,
                "bandwidth_demand": 0, "active": True,
            },
            "relationships": {
                "topology": {"class": "Topology", "id": 1},
                "active_flows": [], "applications": [],
                "nodes": [
                    {"class": "NetworkSwitch", "id": a},
                    {"class": "NetworkSwitch", "id": b},
                ],
            },
        })

    ds["BaseStation"] = []
    # Track user IDs globally
    user_id_counter = 1
    for s in SERVER_DEFS:
        sid = s["id"]
        num_users = SERVER_CONFIGS[sid]["users"]
        user_ids = list(range(user_id_counter, user_id_counter + num_users))
        user_id_counter += num_users
        ds["BaseStation"].append({
            "attributes": {
                "id": sid, "coordinates": s["coords"], "wireless_delay": 5,
            },
            "relationships": {
                "users": [{"class": "User", "id": uid} for uid in user_ids],
                "edge_servers": [{"class": "EdgeServer", "id": sid}],
                "network_switch": {"class": "NetworkSwitch", "id": sid},
            },
        })

    ds["EdgeServer"] = []
    for s in SERVER_DEFS:
        sid = s["id"]
        has_registry = (sid == 1)
        ds["EdgeServer"].append({
            "attributes": {
                "id": sid, "available": True, "model_name": "E5507",
                "cpu": 8, "memory": 8192, "disk": 131072,
                "cpu_demand": 0, "memory_demand": 0, "disk_demand": 0,
                "coordinates": s["coords"],
                "max_concurrent_layer_downloads": 3, "active": True,
                "power_model_parameters": {
                    "max_power_consumption": 218,
                    "static_power_percentage": 0.3073,
                },
            },
            "relationships": {
                "power_model": "LinearServerPowerModel",
                "base_station":  {"class": "BaseStation",  "id": sid},
                "network_switch": {"class": "NetworkSwitch", "id": sid},
                "services": [],
                "container_layers":     [{"class": "ContainerLayer",     "id": 1}] if has_registry else [],
                "container_images":     [{"class": "ContainerImage",     "id": 1}] if has_registry else [],
                "container_registries": [{"class": "ContainerRegistry",  "id": 1}] if has_registry else [],
            },
        })

    ds["ContainerLayer"] = [{
        "attributes": {"id": 1, "digest": LAYER_DIGEST, "size": 10,
                       "instruction": "ADD file:minimal_layer"},
        "relationships": {"server": {"class": "EdgeServer", "id": 1}},
    }]
    ds["ContainerImage"] = [{
        "attributes": {"id": 1, "name": "minimal-app", "tag": "latest",
                       "digest": IMAGE_DIGEST,
                       "layers_digests": [LAYER_DIGEST], "architecture": ""},
        "relationships": {"server": {"class": "EdgeServer", "id": 1}},
    }]
    ds["ContainerRegistry"] = [{
        "attributes": {"id": 1, "cpu_demand": 0, "memory_demand": 0},
        "relationships": {"server": {"class": "EdgeServer", "id": 1}},
    }]

    ds["Service"] = []
    service_id_counter = 1
    for s in SERVER_DEFS:
        sid = s["id"]
        num_services = SERVER_CONFIGS[sid]["services"]
        for j in range(num_services):
            svc_id = service_id_counter
            service_id_counter += 1
            # Randomize CPU and memory demands
            cpu_d  = random.randint(1, 3)
            mem_d  = random.randint(512, 2048)
            ds["Service"].append({
                "attributes": {
                    "id": svc_id, "label": f"svc{j}-{sid}", "state": 0,
                    "_available": True, "cpu_demand": cpu_d,
                    "memory_demand": mem_d, "image_digest": IMAGE_DIGEST,
                },
                "relationships": {
                    "application": {"class": "Application", "id": svc_id},
                    "server": None,
                },
            })

    ds["Application"] = []
    app_to_users = {}  # app_id -> [user_ids]
    user_id_counter = 1
    app_id_start = 1
    
    for s in SERVER_DEFS:
        sid = s["id"]
        num_users = SERVER_CONFIGS[sid]["users"]
        num_services = SERVER_CONFIGS[sid]["services"]
        
        # Initialize apps for this server
        for j in range(num_services):
            app_id = app_id_start + j
            if app_id not in app_to_users:
                app_to_users[app_id] = []
        
        # Assign users to apps (round-robin)
        for j in range(num_users):
            uid = user_id_counter
            user_id_counter += 1
            app_offset = j % num_services
            app_id = app_id_start + app_offset
            app_to_users[app_id].append(uid)
        
        app_id_start += num_services
    
    # Now create Applications with correct user mappings
    app_id_counter = 1
    for s in SERVER_DEFS:
        sid = s["id"]
        num_services = SERVER_CONFIGS[sid]["services"]
        for j in range(num_services):
            app_id = app_id_counter
            app_id_counter += 1
            user_ids = app_to_users.get(app_id, [])
            ds["Application"].append({
                "attributes": {"id": app_id, "label": f"App-{app_id}"},
                "relationships": {
                    "services": [{"class": "Service", "id": app_id}],
                    "users": [{"class": "User", "id": uid} for uid in user_ids],
                },
            })

    ds["User"] = []
    user_id_counter = 1
    app_id_start = 1 
    
    for s in SERVER_DEFS:
        sid = s["id"]
        coords = s["coords"]
        trace = traces[tuple(coords)]
        num_users = SERVER_CONFIGS[sid]["users"]
        num_services = SERVER_CONFIGS[sid]["services"]
        
        for j in range(num_users):
            uid = user_id_counter
            user_id_counter += 1
            # Each user maps to one application (round-robin within server's apps)
            app_offset = j % num_services
            app_id = app_id_start + app_offset  # Reference server's apps
            
            # Randomize deadline SLA per user
            deadline_sla = random.randint(DEADLINE_MIN, DEADLINE_MAX)
            
            ds["User"].append({
                "attributes": {
                    "id": uid, "coordinates": list(coords),
                    "coordinates_trace": trace,
                    "delays":       {str(app_id): None},
                    "delay_slas":   {str(app_id): deadline_sla},
                    "communication_paths": {},
                    "making_requests": {str(app_id): {"1": True}},
                },
                "relationships": {
                    "access_patterns": {
                        str(app_id): {
                            "class": "CircularDurationAndIntervalAccessPattern",
                            "id": uid,
                        }
                    },
                    "mobility_model": "pathway",
                    "applications": [{"class": "Application", "id": app_id}],
                    "base_station":  {"class": "BaseStation",  "id": sid},
                },
            })
        
        # Move to next server's app range
        app_id_start += num_services

    # Build CircularDurationAndIntervalAccessPattern for all users
    ds["CircularDurationAndIntervalAccessPattern"] = []
    user_id_counter = 1
    app_id_start = 1 
    
    for s in SERVER_DEFS:
        sid = s["id"]
        num_users = SERVER_CONFIGS[sid]["users"]
        num_services = SERVER_CONFIGS[sid]["services"]
        
        for j in range(num_users):
            uid = user_id_counter
            user_id_counter += 1
            app_offset = j % num_services
            app_id = app_id_start + app_offset
            
            ds["CircularDurationAndIntervalAccessPattern"].append({
                "attributes": {
                    "id": uid,
                    "duration_values": [float("inf")],
                    "interval_values": [0],
                    "history": [{
                        "start": 1, "end": float("inf"),
                        "duration": float("inf"), "waiting_time": 0,
                        "access_time": 0, "interval": 0,
                        "next_access": float("inf"),
                    }],
                },
                "relationships": {
                    "user": {"class": "User",        "id": uid},
                    "app":  {"class": "Application", "id": app_id},
                },
            })
        
        # Move to next server's app range
        app_id_start += num_services
    ds["RandomDurationAndIntervalAccessPattern"] = []
    return ds


dataset = _build_dataset()


def targeted_placement(parameters={}):
    servers = {s.id: s for s in EdgeServer.all()}
    services_by_server = {}
    
    # Group services by their target server
    for svc in Service.all():
        if svc.server is not None:
            continue
        
        # Parse service label to find server ID (format: "svcX-ServerID")
        try:
            parts = svc.label.split("-")
            if len(parts) >= 2:
                target_sid = int(parts[-1])
            else:
                # Fallback: distribute evenly
                target_sid = (svc.id % len(servers)) + 1
        except:
            target_sid = (svc.id % len(servers)) + 1
        
        if target_sid not in services_by_server:
            services_by_server[target_sid] = []
        services_by_server[target_sid].append(svc)
    
    # Place services on their target servers
    for target_sid, svcs in services_by_server.items():
        target = servers.get(target_sid)
        if not target:
            continue
        
        for svc in svcs:
            if target.has_capacity_to_host(svc):
                svc.server = target
                svc._available = True
                target.cpu_demand += svc.cpu_demand
                target.memory_demand += svc.memory_demand
                if svc not in target.services:
                    target.services.append(svc)


def stopping_criterion(model):
    return model.schedule.steps >= NUM_STEPS


def analyze_simulation_results(log_dir="logs", output_dir="Analysis"):
    print("\n" + "=" * 78)
    print("  ANALYZING SIMULATION RESULTS")
    print("=" * 78)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # --─ Load all logs ------------------------------------------─
    print("  Loading logs...")
    logs = {}
    log_files = {
        "EdgeServer": "EdgeServer.msgpack",
        "FaultyEdgeServer": "FaultyEdgeServer.msgpack",
        "Service": "Service.msgpack",
        "User": "User.msgpack",
        "NetworkSwitch": "NetworkSwitch.msgpack",
    }
    
    for name, fname in log_files.items():
        fpath = os.path.join(log_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                # Read all rows from msgpack
                data = msgpack.unpackb(f.read(), raw=False)
                if isinstance(data, list) and len(data) > 0:
                    logs[name] = pd.DataFrame(data)
                    print(f"    OK {fname}: {len(logs[name])} records")
                else:
                    logs[name] = pd.DataFrame()
                    print(f"    X {fname}: empty or invalid format")
        else:
            logs[name] = pd.DataFrame()
            print(f"    X {fname}: not found")
    
    # --─ Prepare data --------------------------------------------
    has_faulty = not logs["FaultyEdgeServer"].empty
    has_healthy = not logs["EdgeServer"].empty
    
    if not has_faulty and not has_healthy:
        print("  X No server logs found. Skipping analysis.")
        return
    
    # =============================================================
    # Figure 1: Fault Type Comparison (Bar Charts)
    # =============================================================
    if has_faulty:
        print("\n  Generating Figure 1: Fault Type Comparison...")
        df_faulty = logs["FaultyEdgeServer"]
        
        # Aggregate by fault type (latest timestep per server)
        latest_step = df_faulty["Time Step"].max()
        df_latest = df_faulty[df_faulty["Time Step"] == latest_step]
        
        fault_summary = df_latest.groupby("fault_type").agg({
            "Instance ID": "count",
            "requests_received": "sum",
            "requests_processed": "sum",
            "requests_failed": "sum",
            "delayed_requests": "sum",
            "dropped_requests": "sum",
            "rejected_requests": "sum",
            "false_reports_count": "sum",
            "deadline_violations": "sum",
        }).reset_index()
        fault_summary.columns = ["Fault Type", "Count", "Received", "Processed", 
                                 "Failed", "Delayed", "Dropped", "Rejected", "False Reports", "Deadline Miss"]
        
        # Create bar chart grid
        fig, axes = plt.subplots(2, 5, figsize=(24, 10))
        fig.suptitle("Fault Type Comparison — Request & Fault Metrics", fontsize=16, fontweight="bold")
        
        metrics = [
            ("Count", "Number of Servers"),
            ("Received", "Total Requests Received"),
            ("Processed", "Requests Successfully Processed"),
            ("Failed", "Requests Failed"),
            ("Delayed", "Delayed Requests"),
            ("Dropped", "Dropped Requests"),
            ("Rejected", "Rejected Requests"),
            ("False Reports", "False Resource Reports"),
            ("Deadline Miss", "Deadline Violations"),
        ]
        
        for idx, (col, title) in enumerate(metrics):
            row = idx // 5
            col_idx = idx % 5
            ax = axes[row, col_idx]
            colors = plt.cm.Set3(np.linspace(0, 1, len(fault_summary)))
            bars = ax.bar(range(len(fault_summary)), fault_summary[col], color=colors)
            ax.set_title(title, fontweight="bold")
            ax.set_xticks(range(len(fault_summary)))
            ax.set_xticklabels(fault_summary["Fault Type"], rotation=45, ha="right", fontsize=8)
            ax.grid(axis="y", alpha=0.3)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # Hide the last subplot (2x5 grid has 10 slots, we use 9)
        axes[1, 4].axis('off')
        
        plt.tight_layout()
        fig1_path = os.path.join(output_dir, "fig1_fault_type_comparison.png")
        plt.savefig(fig1_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    OK Saved: {fig1_path}")
        
        # Save summary table
        table1_path = os.path.join(output_dir, "table1_fault_summary.csv")
        fault_summary.to_csv(table1_path, index=False)
        print(f"    OK Saved: {table1_path}")
    
    # =============================================================
    # Figure 2: Time Series — Resource Utilization
    # =============================================================
    print("\n  Generating Figure 2: Time Series — Resource Utilization...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Time Series: Resource Utilization (Healthy vs Faulty)", fontsize=16, fontweight="bold")
    
    # (actual_col, reported_col, title, is_list_col)
    metrics_ts = [
        ("CPU Demand", "reported_cpu_demand", "CPU Demand (cores)", False),
        ("RAM Demand", "reported_memory_demand", "Memory Demand (MB)", False),
        ("Power Consumption", None, "Power Consumption (W)", False),
        ("Services", None, "Hosted Services", True),  # True means count list length
    ]
    
    for idx, (actual_col, reported_col, title, is_list_col) in enumerate(metrics_ts):
        ax = axes[idx // 2, idx % 2]
        
        if has_healthy and actual_col in logs["EdgeServer"].columns:
            df_h = logs["EdgeServer"].copy()
            if is_list_col:
                # Count list lengths per server, then average
                df_h["_count"] = df_h[actual_col].apply(lambda x: len(x) if isinstance(x, list) else 0)
                df_h_ts = df_h.groupby("Time Step")["_count"].mean()
            else:
                df_h_ts = df_h.groupby("Time Step")[actual_col].mean()
            ax.plot(df_h_ts.index, df_h_ts.values, label="Healthy (avg)", 
                   linewidth=2, color="green", marker="o", markersize=3, alpha=0.7)
        
        if has_faulty and actual_col in logs["FaultyEdgeServer"].columns:
            df_f = logs["FaultyEdgeServer"].copy()
            
            # Check if any faulty servers have false_resource_reporting fault type
            has_false_reporting = False
            if "fault_type" in df_f.columns:
                has_false_reporting = "false_resource_reporting" in df_f["fault_type"].values
            
            # Plot actual values
            if is_list_col:
                # Count list lengths per server, then average
                df_f["_count"] = df_f[actual_col].apply(lambda x: len(x) if isinstance(x, list) else 0)
                df_f_ts_actual = df_f.groupby("Time Step")["_count"].mean()
            else:
                df_f_ts_actual = df_f.groupby("Time Step")[actual_col].mean()
            ax.plot(df_f_ts_actual.index, df_f_ts_actual.values, label="Faulty - Actual (avg)", 
                   linewidth=2, color="red", marker="s", markersize=3, alpha=0.7)
            
            # For false_resource_reporting, also plot reported values
            if reported_col and reported_col in df_f.columns and has_false_reporting:
                df_f_ts_reported = df_f.groupby("Time Step")[reported_col].mean()
                ax.plot(df_f_ts_reported.index, df_f_ts_reported.values, 
                       label="Faulty - Reported (inflated)", 
                       linewidth=2, color="orange", linestyle="--", marker="^", markersize=3, alpha=0.7)
        
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Time Step")
        ax.set_ylabel(title.split("(")[1].strip(")") if "(" in title else title)
        ax.legend()
        ax.grid(alpha=0.3)
    
    plt.tight_layout()
    fig2_path = os.path.join(output_dir, "fig2_time_series_resources.png")
    plt.savefig(fig2_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    OK Saved: {fig2_path}")
    
    # =============================================================
    # Figure 3: Request Processing Over Time
    # =============================================================
    if has_faulty:
        print("\n  Generating Figure 3: Request Processing Timeline...")
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle("Request Processing Evolution (Faulty Servers)", fontsize=16, fontweight="bold")
        
        request_metrics = [
            ("requests_received", "Requests Received"),
            ("requests_processed", "Requests Processed"),
            ("requests_failed", "Requests Failed"),
            ("delayed_requests", "Delayed Requests"),
        ]
        
        df_faulty = logs["FaultyEdgeServer"]
        
        for idx, (col, title) in enumerate(request_metrics):
            ax = axes[idx // 2, idx % 2]
            
            # Plot per fault type
            for ft in df_faulty["fault_type"].unique():
                df_ft = df_faulty[df_faulty["fault_type"] == ft]
                ts_data = df_ft.groupby("Time Step")[col].sum()
                ax.plot(ts_data.index, ts_data.values, label=ft, linewidth=2, marker="o", markersize=3)
            
            ax.set_title(title, fontweight="bold")
            ax.set_xlabel("Time Step")
            ax.set_ylabel("Count")
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)
        
        plt.tight_layout()
        fig3_path = os.path.join(output_dir, "fig3_request_processing_timeline.png")
        plt.savefig(fig3_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    OK Saved: {fig3_path}")
    
    # =============================================================
    # Figure 4: Resource Reporting Accuracy (Actual vs Reported)
    # =============================================================
    if has_faulty:
        print("\n  Generating Figure 4: Resource Reporting Accuracy...")
        
        df_faulty = logs["FaultyEdgeServer"]
        df_false_rpt = df_faulty[df_faulty["fault_type"] == "false_resource_reporting"]
        
        if not df_false_rpt.empty and "reported_cpu_demand" in df_false_rpt.columns:
            fig, axes = plt.subplots(2, 2, figsize=(16, 10))
            fig.suptitle("Resource Reporting Accuracy: Actual vs Reported (False Reporting Attack)", 
                        fontsize=16, fontweight="bold")
            
            # Track false reports over time
            false_rpt_ts = df_false_rpt.groupby("Time Step")["false_reports_count"].sum()
            
            ax = axes[0, 0]
            ax.plot(false_rpt_ts.index, false_rpt_ts.values, linewidth=2, color="darkred", marker="o", markersize=4)
            ax.set_title("Cumulative False Resource Reports", fontweight="bold")
            ax.set_xlabel("Time Step")
            ax.set_ylabel("False Reports Count")
            ax.grid(alpha=0.3)
            ax.fill_between(false_rpt_ts.index, false_rpt_ts.values, alpha=0.2, color="darkred")
            
            # CPU: Actual vs Reported comparison
            ax = axes[0, 1]
            cpu_actual = df_false_rpt["CPU Demand"].values
            cpu_reported = df_false_rpt["reported_cpu_demand"].values
            cpu_diff = cpu_reported - cpu_actual
            
            # Scatter plot
            scatter = ax.scatter(cpu_actual, cpu_reported, alpha=0.3, c=cpu_diff, cmap='RdYlGn_r', s=20)
            ax.plot([0, cpu_actual.max()], [0, cpu_actual.max()], 'k--', linewidth=1, label='Truth Line')
            ax.set_title("CPU: Actual vs Reported", fontweight="bold")
            ax.set_xlabel("Actual CPU Demand (cores)")
            ax.set_ylabel("Reported CPU Demand (cores)")
            ax.legend()
            ax.grid(alpha=0.3)
            plt.colorbar(scatter, ax=ax, label='Inflation (cores)')
            
            # Memory: Actual vs Reported comparison
            ax = axes[1, 0]
            mem_actual = df_false_rpt["RAM Demand"].values
            mem_reported = df_false_rpt["reported_memory_demand"].values
            mem_diff = mem_reported - mem_actual
            
            scatter = ax.scatter(mem_actual, mem_reported, alpha=0.3, c=mem_diff, cmap='RdYlGn_r', s=20)
            ax.plot([0, mem_actual.max()], [0, mem_actual.max()], 'k--', linewidth=1, label='Truth Line')
            ax.set_title("Memory: Actual vs Reported", fontweight="bold")
            ax.set_xlabel("Actual Memory Demand (MB)")
            ax.set_ylabel("Reported Memory Demand (MB)")
            ax.legend()
            ax.grid(alpha=0.3)
            plt.colorbar(scatter, ax=ax, label='Inflation (MB)')
            
            # Inflation factor distribution
            ax = axes[1, 1]
            cpu_inflation = (cpu_reported / cpu_actual - 1) * 100
            cpu_inflation = cpu_inflation[np.isfinite(cpu_inflation) & (cpu_actual > 0)]
            
            ax.hist(cpu_inflation, bins=30, color='coral', alpha=0.7, edgecolor='black', label='CPU Inflation')
            ax.axvline(x=0, color='green', linestyle='--', linewidth=2, label='No Inflation')
            ax.set_title("Resource Inflation Distribution", fontweight="bold")
            ax.set_xlabel("Inflation (%)")
            ax.set_ylabel("Frequency")
            ax.legend()
            ax.grid(axis="y", alpha=0.3)
            
            plt.tight_layout()
            fig4_path = os.path.join(output_dir, "fig4_resource_reporting_accuracy.png")
            plt.savefig(fig4_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"    OK Saved: {fig4_path}")
        else:
            print("    [INFO] No false_resource_reporting servers found, skipping Figure 4")
    
    # =============================================================
    # Figure 5: Load Balancing Distribution
    # =============================================================
    if has_healthy or has_faulty:
        print("\n  Generating Figure 5: Load Balancing Distribution...")
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle("Load Balancing: Service Distribution & CPU Load", fontsize=16, fontweight="bold")
        
        # Combine all servers
        all_servers = []
        if has_healthy:
            df_h = logs["EdgeServer"].copy()
            df_h["server_type"] = "Healthy"
            all_servers.append(df_h)
        if has_faulty:
            df_f = logs["FaultyEdgeServer"].copy()
            df_f["server_type"] = "Faulty (" + df_f["fault_type"] + ")"
            all_servers.append(df_f)
        
        df_all = pd.concat(all_servers, ignore_index=True)
        latest_step = df_all["Time Step"].max()
        df_latest = df_all[df_all["Time Step"] == latest_step]
        
        # Convert Services column to count
        df_latest["Services_count"] = df_latest["Services"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        
        # Service distribution
        ax = axes[0]
        service_dist = df_latest.groupby("server_type")["Services_count"].sum().sort_values(ascending=False)
        colors = plt.cm.Paired(np.linspace(0, 1, len(service_dist)))
        bars = ax.bar(range(len(service_dist)), service_dist.values, color=colors)
        ax.set_title("Total Services Hosted by Server Type", fontweight="bold")
        ax.set_xticks(range(len(service_dist)))
        ax.set_xticklabels(service_dist.index, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Number of Services")
        ax.grid(axis="y", alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # CPU load distribution
        ax = axes[1]
        cpu_loads = df_latest.groupby("server_type")["CPU Demand"].mean().sort_values(ascending=False)
        colors = plt.cm.Paired(np.linspace(0, 1, len(cpu_loads)))
        bars = ax.bar(range(len(cpu_loads)), cpu_loads.values, color=colors)
        ax.set_title("Average CPU Load by Server Type", fontweight="bold")
        ax.set_xticks(range(len(cpu_loads)))
        ax.set_xticklabels(cpu_loads.index, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("CPU Demand (cores)")
        ax.grid(axis="y", alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        fig5_path = os.path.join(output_dir, "fig5_load_balancing.png")
        plt.savefig(fig5_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    OK Saved: {fig5_path}")
    
    # =============================================================
    # Figure 6: Network Traffic & Power Consumption
    # =============================================================
    print("\n  Generating Figure 6: Network & Power Analysis...")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Network Traffic & Power Consumption Analysis", fontsize=16, fontweight="bold")
    
    # Network switch power over time
    if not logs["NetworkSwitch"].empty:
        ax = axes[0]
        df_net = logs["NetworkSwitch"]
        net_power_ts = df_net.groupby("Time Step")["Power Consumption"].sum()
        ax.plot(net_power_ts.index, net_power_ts.values, linewidth=2, color="blue", marker="o", markersize=3)
        ax.set_title("Total Network Power Consumption", fontweight="bold")
        ax.set_xlabel("Time Step")
        ax.set_ylabel("Power (W)")
        ax.grid(alpha=0.3)
        ax.fill_between(net_power_ts.index, net_power_ts.values, alpha=0.2, color="blue")
    else:
        axes[0].text(0.5, 0.5, "No NetworkSwitch data", ha="center", va="center", fontsize=12)
        axes[0].set_title("Total Network Power Consumption", fontweight="bold")
    
    # Server power comparison (healthy vs faulty)
    ax = axes[1]
    power_data = []
    labels = []
    
    if has_healthy:
        power_data.append(logs["EdgeServer"]["Power Consumption"].mean())
        labels.append("Healthy Servers")
    
    if has_faulty:
        df_faulty = logs["FaultyEdgeServer"]
        for ft in df_faulty["fault_type"].unique():
            df_ft = df_faulty[df_faulty["fault_type"] == ft]
            power_data.append(df_ft["Power Consumption"].mean())
            labels.append(ft)
    
    colors = plt.cm.Set2(np.linspace(0, 1, len(power_data)))
    bars = ax.bar(range(len(power_data)), power_data, color=colors)
    ax.set_title("Average Power Consumption by Server Type", fontweight="bold")
    ax.set_xticks(range(len(power_data)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Power (W)")
    ax.grid(axis="y", alpha=0.3)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    fig6_path = os.path.join(output_dir, "fig6_network_power.png")
    plt.savefig(fig6_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    OK Saved: {fig6_path}")
    
    # =============================================================
    # Figure 7: Impact Severity Visualization (Preview)
    # =============================================================
    if has_faulty and has_healthy:
        print("\n  Generating Figure 7: Impact Severity Preview...")
        
        df_f_all = logs["FaultyEdgeServer"]
        latest_step = df_f_all["Time Step"].max()
        df_f_latest = df_f_all[df_f_all["Time Step"] == latest_step]
        
        # Calculate quick severity metrics per fault type
        fault_types = df_f_latest["fault_type"].unique()
        severity_preview = []
        
        for ft in fault_types:
            df_ft = df_f_latest[df_f_latest["fault_type"] == ft]
            recv = df_ft["requests_received"].sum()
            proc = df_ft["requests_processed"].sum()
            fail = df_ft["requests_failed"].sum()
            
            success_rate = (proc / recv * 100) if recv > 0 else 100
            failure_rate = (fail / recv * 100) if recv > 0 else 0
            
            severity_preview.append({
                "fault_type": ft,
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "total_faults": df_ft["delayed_requests"].sum() + df_ft["dropped_requests"].sum() + 
                               df_ft["rejected_requests"].sum() + df_ft["false_reports_count"].sum()
            })
        
        if severity_preview:
            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            fig.suptitle("Impact Severity Preview — Key Metrics by Fault Type", fontsize=16, fontweight="bold")
            
            df_sev = pd.DataFrame(severity_preview)
            fault_labels = df_sev["fault_type"].values
            
            # Success Rate Comparison
            ax = axes[0]
            colors = plt.cm.RdYlGn(df_sev["success_rate"] / 100)
            bars = ax.bar(range(len(df_sev)), df_sev["success_rate"], color=colors, alpha=0.8)
            ax.set_title("Success Rate", fontweight="bold")
            ax.set_xticks(range(len(df_sev)))
            ax.set_xticklabels(fault_labels, rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("Success Rate (%)")
            ax.set_ylim(0, 105)
            ax.axhline(y=100, color='green', linestyle='--', linewidth=1, label='Healthy Baseline')
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3, axis='y')
            
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
                       ha='center', va='bottom', fontsize=8)
            
            # Failure Rate Comparison
            ax = axes[1]
            bars = ax.bar(range(len(df_sev)), df_sev["failure_rate"], color='lightcoral', alpha=0.8)
            ax.set_title("Failure Rate", fontweight="bold")
            ax.set_xticks(range(len(df_sev)))
            ax.set_xticklabels(fault_labels, rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("Failure Rate (%)")
            ax.grid(alpha=0.3, axis='y')
            
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
                       ha='center', va='bottom', fontsize=8)
            
            # Total Faults Triggered
            ax = axes[2]
            bars = ax.bar(range(len(df_sev)), df_sev["total_faults"], color='darkred', alpha=0.8)
            ax.set_title("Total Faults Triggered", fontweight="bold")
            ax.set_xticks(range(len(df_sev)))
            ax.set_xticklabels(fault_labels, rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("Total Fault Count")
            ax.grid(alpha=0.3, axis='y')
            
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height, f'{int(height)}',
                       ha='center', va='bottom', fontsize=8)
            
            plt.tight_layout()
            fig7_path = os.path.join(output_dir, "fig7_impact_severity_preview.png")
            plt.savefig(fig7_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"    OK Saved: {fig7_path}")
    
    # =============================================================
    # Table 2: Overall Summary Statistics
    # =============================================================
    print("\n  Generating Table 2: Overall Summary Statistics...")
    
    summary_stats = []
    
    if has_healthy:
        df_h = logs["EdgeServer"]
        latest_step = df_h["Time Step"].max()
        df_h_latest = df_h[df_h["Time Step"] == latest_step]
        
        # Convert Services to counts
        df_h_latest["Services_count"] = df_h_latest["Services"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        
        summary_stats.append({
            "Server Type": "healthy",
            "Count": len(df_h_latest),
            "Avg CPU (%)": (df_h_latest["CPU Demand"] / df_h_latest["CPU"] * 100).mean(),
            "Avg Memory (%)": (df_h_latest["RAM Demand"] / df_h_latest["RAM"] * 100).mean(),
            "Avg Power (W)": df_h_latest["Power Consumption"].mean(),
            "Total Services": df_h_latest["Services_count"].sum(),
            "Requests Recv": 0,  # not tracked for healthy
            "Requests Proc": 0,
            "Requests Failed": 0,
            "Deadline Missed": 0,
            "Avg Proc Time (ms)": 10,  # baseline assumption
            "Success Rate (%)": 100.0,
            "Deadline Met Rate (%)": 100.0,
        })
    
    if has_faulty:
        df_f = logs["FaultyEdgeServer"]
        latest_step = df_f["Time Step"].max()
        df_f_latest = df_f[df_f["Time Step"] == latest_step]
        
        # Convert Services to counts
        df_f_latest["Services_count"] = df_f_latest["Services"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        
        for ft in df_f_latest["fault_type"].unique():
            df_ft = df_f_latest[df_f_latest["fault_type"] == ft]
            recv = df_ft["requests_received"].sum()
            proc = df_ft["requests_processed"].sum()
            fail = df_ft["requests_failed"].sum()
            deadlines = df_ft["deadline_violations"].sum()
            success_rate = (proc / recv * 100) if recv > 0 else 0
            deadline_met_rate = ((proc - deadlines) / proc * 100) if proc > 0 else 100
            avg_proc_time = df_ft["avg_processing_time"].mean()
            
            summary_stats.append({
                "Server Type": ft,
                "Count": len(df_ft),
                "Avg CPU (%)": (df_ft["CPU Demand"] / df_ft["CPU"] * 100).mean(),
                "Avg Memory (%)": (df_ft["RAM Demand"] / df_ft["RAM"] * 100).mean(),
                "Avg Power (W)": df_ft["Power Consumption"].mean(),
                "Total Services": df_ft["Services_count"].sum(),
                "Requests Recv": recv,
                "Requests Proc": proc,
                "Requests Failed": fail,
                "Deadline Missed": deadlines,
                "Avg Proc Time (ms)": avg_proc_time,
                "Success Rate (%)": success_rate,
                "Deadline Met Rate (%)": deadline_met_rate,
            })
    
    df_summary = pd.DataFrame(summary_stats)
    table2_path = os.path.join(output_dir, "table2_overall_summary.csv")
    df_summary.to_csv(table2_path, index=False)
    print(f"    OK Saved: {table2_path}")
    
    # Print summary to console
    print("\n  Summary Statistics:")
    print(df_summary.to_string(index=False))
    
    # =============================================================
    # Table 3: Impact Severity Analysis
    # =============================================================
    if has_faulty and has_healthy:
        print("\n  Generating Table 3: Impact Severity Analysis...")
        
        # Get healthy baseline (aggregate metrics)
        df_h_all = logs["EdgeServer"]
        latest_step = df_h_all["Time Step"].max()
        df_h_latest = df_h_all[df_h_all["Time Step"] == latest_step]
        
        # For healthy servers, we don't track requests, so we'll use fault data for comparison
        # Get aggregate healthy baseline from all timesteps if available
        h_count = len(df_h_latest)
        
        # Calculate baseline from fault data (since healthy doesn't track requests)
        df_f_all = logs["FaultyEdgeServer"]
        df_f_latest = df_f_all[df_f_all["Time Step"] == latest_step]
        
        # We'll use the average of all faulty types as comparison baseline
        # Or better: assume healthy would have 0 failures
        healthy_baseline = {
            "throughput_per_server": 1,  # placeholder
            "avg_latency": 10,  # baseline assumption
            "success_rate": 100.0,
            "deadline_met": 100.0,
            "failure_rate": 0.0,
        }
        
        # Try to estimate healthy throughput from healthy server count
        if h_count > 0:
            # Estimate based on total requests across all faulty servers
            total_recv = df_f_latest["requests_received"].sum()
            total_servers = len(df_f_latest)
            if total_servers > 0:
                avg_recv_per_server = total_recv / total_servers
                # Healthy servers should process all requests successfully
                healthy_baseline["throughput_per_server"] = avg_recv_per_server
        
        # Calculate impact for each fault type
        impact_data = []
        for ft in df_f_latest["fault_type"].unique():
            df_ft = df_f_latest[df_f_latest["fault_type"] == ft]
            if df_ft.empty:
                continue
            
            # Aggregate metrics for this fault type
            recv = df_ft["requests_received"].sum()
            proc = df_ft["requests_processed"].sum()
            fail = df_ft["requests_failed"].sum()
            num_servers = len(df_ft)
            
            # Calculate per-server metrics for fair comparison
            throughput_per_server = proc / num_servers if num_servers > 0 else 0
            success_rate = (proc / recv * 100) if recv > 0 else 100
            failure_rate = (fail / recv * 100) if recv > 0 else 0
            
            # Expected healthy throughput for same number of servers
            expected_healthy_throughput = healthy_baseline["throughput_per_server"] * num_servers
            
            # Calculate deadline metrics
            deadlines_missed = df_ft["deadline_violations"].sum()
            deadline_met_rate = ((proc - deadlines_missed) / proc * 100) if proc > 0 else 100
            
            # Calculate impact (degradation from baseline)
            throughput_degradation = max(0, (expected_healthy_throughput - proc) / expected_healthy_throughput * 100) if expected_healthy_throughput > 0 else 0
            avg_proc_time = df_ft["avg_processing_time"].mean()
            latency_increase = max(0, (avg_proc_time - healthy_baseline["avg_latency"]) / healthy_baseline["avg_latency"] * 100) if healthy_baseline["avg_latency"] > 0 else 0
            success_drop = max(0, healthy_baseline["success_rate"] - success_rate)
            deadline_drop = max(0, healthy_baseline["deadline_met"] - deadline_met_rate)
            failure_increase = max(0, failure_rate - healthy_baseline["failure_rate"])
            
            # Composite severity score (weighted by importance)
            # Balanced scoring: throughput, latency, success rate, deadline violations, failures
            severity = (throughput_degradation * 0.25 + latency_increase * 0.20 + 
                       success_drop * 0.20 + deadline_drop * 0.20 + failure_increase * 0.15)
            
            impact_data.append({
                "Fault Type": ft,
                "Throughput Degradation (%)": throughput_degradation,
                "Latency Increase (%)": latency_increase,
                "Success Rate Drop (%)": success_drop,
                "Deadline Met Drop (%)": deadline_drop,
                "Failure Rate Increase (%)": failure_increase,
                "Severity Score": severity,
            })
        
        impact_df = pd.DataFrame(impact_data)
        
        if not impact_df.empty:
            table3_path = os.path.join(output_dir, "table3_impact_severity.csv")
            impact_df.to_csv(table3_path, index=False)
            print(f"    OK Saved: {table3_path}")
            
            # Print impact severity to console
            print("\n  Impact Severity Analysis:")
            print(impact_df.to_string(index=False))
        else:
            print("    [INFO] No fault data to calculate impact severity")
    
    print("\n" + "=" * 78)
    print(f"  ANALYSIS COMPLETE — {len([f for f in os.listdir(output_dir) if f.endswith('.png')])} figures, {len([f for f in os.listdir(output_dir) if f.endswith('.csv')])} tables saved to '{output_dir}/'")
    print("=" * 78)


if __name__ == "__main__":

    print("=" * 78)
    print("  SCALED EDGESIMPY SIMULATION — Dynamic Byzantine Fault Injection")
    print("=" * 78)
    print(f"  Configuration:")
    print(f"    * Servers          : {NUM_SERVERS} total ({NUM_FAULTY} faulty = {FAULTY_PERCENTAGE}%)")
    print(f"    * Topology         : {int(np.ceil(np.sqrt(NUM_SERVERS)))}x{int(np.ceil(NUM_SERVERS/np.ceil(np.sqrt(NUM_SERVERS))))} grid")
    print(f"    * Users            : {NUM_SERVERS * 2} (2 per server)")
    print(f"    * Services         : {NUM_SERVERS * 2} (2 per server)")
    print(f"    * Duration         : {NUM_STEPS} steps")
    print(f"    * Random seed      : {RANDOM_SEED if RANDOM_SEED is not None else 'None (random)'}")
    print(f"    * Fault types      : {', '.join(FAULT_TYPES)}")
    print("=" * 78)
    print()

    # Clean previous logs
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    if os.path.exists(log_dir):
        for f in os.listdir(log_dir):
            if f.endswith(".msgpack"):
                os.remove(os.path.join(log_dir, f))

    simulator = Simulator(
        dump_interval=DUMP_INTERVAL,
        tick_duration=1,
        tick_unit="seconds",
        stopping_criterion=stopping_criterion,
        resource_management_algorithm=targeted_placement,
    )

    print(f"Loading dataset (NUM_SERVERS={NUM_SERVERS}, FAULTY={NUM_FAULTY}, {FAULTY_PERCENTAGE}%) ...")
    simulator.initialize(input_file=dataset)

    # Convert faulty servers
    faulty_count = 0
    for sdef in SERVER_DEFS:
        if sdef["fault"] is None:
            continue
        srv = next(s for s in EdgeServer.all() if s.id == sdef["id"])
        
        # Generate randomized fault config for this server
        config = generate_fault_config(sdef["fault"])
        
        # Set target application IDs for rejection-based attacks
        sid = sdef["id"]
        num_services = SERVER_CONFIGS[sid]["services"]
        # Calculate app IDs for this server (based on cumulative service count)
        app_start = sum(SERVER_CONFIGS[i]["services"] for i in range(1, sid))
        app_ids = list(range(app_start + 1, app_start + num_services + 1))
        
        if "rejection_config" in config:
            config["rejection_config"]["target_application_ids"] = app_ids
        
        convert_to_faulty(srv, sdef["fault"], config)
        faulty_count += 1
    
    print(f"  Converted {faulty_count} servers to faulty ({faulty_count/NUM_SERVERS*100:.1f}%)")

    print(f"  Edge servers : {len(EdgeServer.all())}")
    print(f"  Services     : {len(Service.all())}")
    print(f"  Users        : {len(User.all())}")
    print(f"  Applications : {len(Application.all())}")

    print(f"\nRunning simulation for {NUM_STEPS} steps ...")
    simulator.run_model()

    print("\n" + "=" * 78)
    print("  SIMULATION RESULTS")
    print("=" * 78)
    print(f"  Steps completed: {simulator.schedule.steps}\n")

    print("  -- Edge Servers Summary --")
    healthy_servers = [s for s in EdgeServer.all() if not isinstance(s, FaultyEdgeServer)]
    faulty_servers = [s for s in EdgeServer.all() if isinstance(s, FaultyEdgeServer)]
    
    print(f"    Total: {len(EdgeServer.all())}  |  Healthy: {len(healthy_servers)}  |  Faulty: {len(faulty_servers)}")
    
    if healthy_servers:
        h_power = np.mean([s.get_power_consumption() for s in healthy_servers])
        h_util = np.mean([(s.cpu_demand/s.cpu*100) if s.cpu else 0 for s in healthy_servers])
        print(f"    Healthy avg: Power={h_power:.1f}W  CPU={h_util:.1f}%")
    
    if faulty_servers:
        f_power = np.mean([s.get_power_consumption() for s in faulty_servers])
        f_util = np.mean([(s.cpu_demand/s.cpu*100) if s.cpu else 0 for s in faulty_servers])
        f_recv = sum(s.requests_received for s in faulty_servers)
        f_proc = sum(s.requests_processed for s in faulty_servers)
        f_fail = sum(s.requests_failed for s in faulty_servers)
        f_deadline_miss = sum(s.deadline_violations for s in faulty_servers)
        print(f"    Faulty avg:  Power={f_power:.1f}W  CPU={f_util:.1f}%")
        print(f"    Faulty total requests: recv={f_recv}  proc={f_proc}  failed={f_fail}  deadline_miss={f_deadline_miss}")

    print("\n  -- Services Summary --")
    total_svcs = len(Service.all())
    placed_svcs = len([s for s in Service.all() if s.server is not None])
    svcs_on_healthy = len([s for s in Service.all() if s.server and not isinstance(s.server, FaultyEdgeServer)])
    svcs_on_faulty = len([s for s in Service.all() if s.server and isinstance(s.server, FaultyEdgeServer)])
    print(f"    Total: {total_svcs}  |  Placed: {placed_svcs}  |  On healthy: {svcs_on_healthy}  |  On faulty: {svcs_on_faulty}")

    print("\n  -- Fault Type Distribution --")
    fault_counts = {}
    for server in EdgeServer.all():
        if isinstance(server, FaultyEdgeServer):
            ft = server.fault_type
            if ft not in fault_counts:
                fault_counts[ft] = {"count": 0, "recv": 0, "proc": 0, "fail": 0, 
                                     "delay": 0, "drop": 0, "reject": 0, "false": 0, "deadline": 0}
            fault_counts[ft]["count"] += 1
            fault_counts[ft]["recv"] += server.requests_received
            fault_counts[ft]["proc"] += server.requests_processed
            fault_counts[ft]["fail"] += server.requests_failed
            fault_counts[ft]["delay"] += server.delayed_requests
            fault_counts[ft]["drop"] += server.dropped_requests
            fault_counts[ft]["reject"] += server.rejected_requests
            fault_counts[ft]["false"] += server.false_reports_count
            fault_counts[ft]["deadline"] += server.deadline_violations
    
    print(f"    {'Fault Type':>28s}  {'Count':>6s}  {'Recv':>7s}  {'Proc':>7s}  "
          f"{'Failed':>7s}  {'Delay':>6s}  {'Drop':>6s}  {'Reject':>6s}  {'False':>6s}  {'SLA Miss':>8s}")
    print("    " + "-" * 113)
    for ft in sorted(fault_counts.keys()):
        fc = fault_counts[ft]
        print(f"    {ft:>28s}  {fc['count']:>6d}  {fc['recv']:>7d}  {fc['proc']:>7d}  "
              f"{fc['fail']:>7d}  {fc['delay']:>6d}  {fc['drop']:>6d}  "
              f"{fc['reject']:>6d}  {fc['false']:>6d}  {fc['deadline']:>8d}")

    print("\n  -- Simulation Logs --")
    if os.path.exists(log_dir):
        for log_file in sorted(os.listdir(log_dir)):
            if not log_file.endswith(".msgpack"):
                continue
            fp = os.path.join(log_dir, log_file)
            try:
                with open(fp, "rb") as f:
                    data = msgpack.unpackb(f.read(), raw=False)
                df = pd.DataFrame(data)
                extra = ""
                if "Power Consumption" in df.columns:
                    extra += f"  pwr={df['Power Consumption'].min():.1f}–{df['Power Consumption'].max():.1f}W"
                if "delayed_requests" in df.columns:
                    extra += f"  delayed={df['delayed_requests'].max()}"
                if "dropped_requests" in df.columns:
                    extra += f"  dropped={df['dropped_requests'].max()}"
                if "rejected_requests" in df.columns:
                    extra += f"  rejected={df['rejected_requests'].max()}"
                if "false_reports_count" in df.columns:
                    extra += f"  false_rpt={df['false_reports_count'].max()}"
                print(f"    {log_file:40s} {len(df):4d} records{extra}")
            except Exception as exc:
                print(f"    {log_file}: error – {exc}")

    print("\n" + "=" * 78)
    print("  Done.")
    print("=" * 78)
    
    analyze_simulation_results(log_dir=log_dir, output_dir=f"Analysis/{NUM_SERVERS}_{FAULTY_PERCENTAGE}_{USERS_MIN}-{USERS_MAX}_{SERVICES_MIN}-{SERVICES_MAX}")
