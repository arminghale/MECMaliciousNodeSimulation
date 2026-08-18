"""
Minimal EdgeSimPy Simulation — All Byzantine Fault Types
=========================================================

Topology:  6 switches in a 4+2 grid, 6 base stations, 6 edge servers
  Server 1 [0,0] — HEALTHY (baseline)
  Server 2 [2,0] — Processing Delay Attack
  Server 3 [4,0] — Request Dropping
  Server 4 [6,0] — False Resource Reporting
  Server 5 [0,2] — Selective Service Rejection
  Server 6 [2,2] — Mixed (all 4 faults combined)

  2 users + 2 services per server  →  12 users, 12 services, 12 apps
  Duration:  100 time steps, dump every 25 steps
"""

import os
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


# ═════════════════════════════════════════════════════════════════
#  FaultyEdgeServer — supports all 4 Byzantine fault types + mixed
# ═════════════════════════════════════════════════════════════════
class EdgeServerWithRequests(_EdgeServer):
    """EdgeServer with request processing simulation (healthy behavior)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # request counters (available on all servers)
        self.requests_received = 0
        self.requests_processed = 0
        self.requests_failed = 0
        self.requests_deadline_missed = 0  # NEW: deadline violations
        self._req_tick = 0
        self._prev_requests_processed = 0  # track delta for network traffic
        # resource usage tracking (actual vs demand)
        self.cpu_usage_history = []  # actual CPU used per step (with efficiency variance)
        self.ram_usage_history = []  # actual RAM used per step (with efficiency variance)
        self.network_bytes_sent = 0
        self.network_bytes_received = 0
        # request deadline tracking
        self._pending_requests = []  # list of (arrival_tick, deadline_ms) tuples
        self._processing_times = []  # track processing times for statistics
        # Resource reporting (for false reporting detection)
        self.actual_cpu_demand_history = []  # ground truth demand
        self.actual_ram_demand_history = []  # ground truth demand
        self.reported_cpu_demand_history = []  # what server reports (can be false)
        self.reported_ram_demand_history = []  # what server reports (can be false)
        # Resource waste tracking
        self.wasted_cpu_cycles = 0  # CPU used for failed requests
        self.wasted_network_bytes = 0  # traffic for failed requests
        self.useful_work_requests = 0  # successfully processed requests

    def step(self):
        self._process_requests()
        self._track_resource_usage()
        super().step()
    
    def _track_resource_usage(self):
        """Track actual resource usage (simulated based on workload)."""
        # Track ground truth demand
        self.actual_cpu_demand_history.append(self.cpu_demand)
        self.actual_ram_demand_history.append(self.memory_demand)
        
        # For healthy servers, reported = actual demand (truthful)
        self.reported_cpu_demand_history.append(self.cpu_demand)
        self.reported_ram_demand_history.append(self.memory_demand)
        
        # Simulate actual usage as percentage of demand with efficiency variance
        cpu_usage = self.cpu_demand * (0.85 + random.random() * 0.15)  # 85-100% of demand
        ram_usage = self.memory_demand * (0.90 + random.random() * 0.10)  # 90-100% of demand
        
        self.cpu_usage_history.append(cpu_usage)
        self.ram_usage_history.append(ram_usage)
        
        # Simulate network traffic (bytes per NEW requests processed this step)
        new_requests = self.requests_processed - self._prev_requests_processed
        if new_requests > 0:
            bytes_per_request = 1024 * 50  # 50KB per request
            self.network_bytes_sent += new_requests * bytes_per_request * 0.3  # 30% sent
            self.network_bytes_received += new_requests * bytes_per_request * 0.7  # 70% received
        self._prev_requests_processed = self.requests_processed

    def _process_requests(self):
        """Synthesize requests per hosted service (healthy behavior)."""
        if not getattr(self, "services", None):
            return
        self._req_tick += 1
        
        # Process pending requests first (check deadlines)
        new_pending = []
        for arrival_tick, deadline_ms in self._pending_requests:
            elapsed_ticks = self._req_tick - arrival_tick
            elapsed_ms = elapsed_ticks * 1  # 1 tick = 1 second = 1000ms (adjusted below)
            processing_time_ms = 10  # base processing time for healthy servers
            
            if elapsed_ticks >= 1:  # Process after 1 tick minimum
                # Track processing time for all completed requests (successful + failed)
                self._processing_times.append(processing_time_ms)
                
                if processing_time_ms > deadline_ms:
                    # Deadline exceeded
                    self.requests_failed += 1
                    self.requests_deadline_missed += 1
                    # Track wasted resources for failed requests
                    self.wasted_cpu_cycles += 0.1
                    self.wasted_network_bytes += 1024 * 50 * 0.5  # partial network waste
                else:
                    # Successfully processed within deadline
                    self.requests_processed += 1
                    self.useful_work_requests += 1
            else:
                # Still waiting to be processed
                new_pending.append((arrival_tick, deadline_ms))
        
        self._pending_requests = new_pending
        
        # Generate new requests every 5 ticks
        if self._req_tick % 5 != 0:
            return

        for svc in self.services:
            if not getattr(svc, "_available", False):
                continue
            for _ in range(3):                # 3 requests per batch
                self.requests_received += 1
                # Assign deadline: 15-25ms (healthy ~10ms OK, delayed 30ms FAIL)
                deadline_ms = 15 + random.random() * 10
                self._pending_requests.append((self._req_tick, deadline_ms))

    def collect(self):
        metrics = super().collect()
        if not isinstance(metrics, dict):
            metrics = {}
        
        # Calculate averages
        cpu_usage_avg = sum(self.cpu_usage_history) / len(self.cpu_usage_history) if self.cpu_usage_history else 0
        ram_usage_avg = sum(self.ram_usage_history) / len(self.ram_usage_history) if self.ram_usage_history else 0
        cpu_actual_avg = sum(self.actual_cpu_demand_history) / len(self.actual_cpu_demand_history) if self.actual_cpu_demand_history else 0
        ram_actual_avg = sum(self.actual_ram_demand_history) / len(self.actual_ram_demand_history) if self.actual_ram_demand_history else 0
        cpu_reported_avg = sum(self.reported_cpu_demand_history) / len(self.reported_cpu_demand_history) if self.reported_cpu_demand_history else 0
        ram_reported_avg = sum(self.reported_ram_demand_history) / len(self.reported_ram_demand_history) if self.reported_ram_demand_history else 0
        avg_processing_time = sum(self._processing_times) / len(self._processing_times) if self._processing_times else 0
        
        # Calculate resource efficiency
        total_requests = self.requests_received if self.requests_received > 0 else 1
        resource_efficiency = (self.useful_work_requests / total_requests * 100) if total_requests > 0 else 100.0
        
        metrics.update({
            "requests_received": self.requests_received,
            "requests_processed": self.requests_processed,
            "requests_failed": self.requests_failed,
            "requests_deadline_missed": self.requests_deadline_missed,
            "avg_processing_time_ms": avg_processing_time,
            "cpu_usage": cpu_usage_avg,  # actual consumption (with efficiency variance)
            "ram_usage": ram_usage_avg,  # actual consumption (with efficiency variance)
            "cpu_demand_actual": cpu_actual_avg,  # ground truth demand
            "ram_demand_actual": ram_actual_avg,  # ground truth demand
            "cpu_demand_reported": cpu_reported_avg,  # what server reports (can be inflated)
            "ram_demand_reported": ram_reported_avg,  # what server reports (can be inflated)
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_received": self.network_bytes_received,
            "network_bytes_total": self.network_bytes_sent + self.network_bytes_received,
            "wasted_cpu_cycles": self.wasted_cpu_cycles,
            "wasted_network_bytes": self.wasted_network_bytes,
            "useful_work_requests": self.useful_work_requests,
            "resource_efficiency": resource_efficiency,
        })
        return metrics


class FaultyEdgeServer(EdgeServerWithRequests):
    """EdgeServer that can inject one or more Byzantine faults."""

    PROCESSING_DELAY_ATTACK    = "processing_delay_attack"
    REQUEST_DROPPING           = "request_dropping"
    FALSE_RESOURCE_REPORTING   = "false_resource_reporting"
    SELECTIVE_SERVICE_REJECTION = "selective_service_rejection"
    MIXED                      = "mixed"

    # -- initialisation ------------------------------------------------
    def _init_fault(self, fault_type=None, fault_config=None):
        self.fault_type = fault_type
        self.fault_config = fault_config or {}
        # fault counters
        self.delayed_requests = 0
        self.dropped_requests = 0
        self.rejected_requests = 0
        self.false_reports_count = 0

    def __init__(self, *args, fault_type=None, fault_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_fault(fault_type, fault_config)

    def _fault_active(self, *types):
        """True if current fault_type matches any of *types* or is MIXED."""
        return self.fault_type in types or self.fault_type == self.MIXED

    # -- simulation step -----------------------------------------------
    def step(self):
        self._process_requests()  # overridden in this class
        self._track_resource_usage()  # inherited from parent
        self._apply_false_resource_tick()
        super(EdgeServerWithRequests, self).step()  # skip parent's step, use grandparent

    def _process_requests(self):
        """Synthesise requests per hosted service and inject faults."""
        if not getattr(self, "services", None):
            return
        self._req_tick += 1
        
        cfg         = self.fault_config
        slowdown    = cfg.get("slowdown_factor", 2.0)
        delay_prob  = cfg.get("delay_probability", 0.4)
        drop_prob   = cfg.get("drop_probability", 0.3)
        base_ms     = cfg.get("base_latency_ms", 10)
        rej_cfg     = cfg.get("rejection_config", {})
        target_apps = rej_cfg.get("target_application_ids", [])
        rej_rate    = rej_cfg.get("rejection_rate", 0.8)
        
        # Process pending requests first (check deadlines)
        new_pending = []
        for arrival_tick, deadline_ms, is_delayed, app_id in self._pending_requests:
            elapsed_ticks = self._req_tick - arrival_tick
            processing_time_ms = base_ms * slowdown if is_delayed else base_ms
            
            if elapsed_ticks >= 1:  # Process after 1 tick minimum
                # Track processing time for all completed requests (including deadline violations)
                self._processing_times.append(processing_time_ms)
                
                if processing_time_ms > deadline_ms:
                    # Deadline exceeded - mark as failed
                    self.requests_failed += 1
                    self.requests_deadline_missed += 1
                    # Track wasted resources for deadline violations
                    self.wasted_cpu_cycles += 0.15 if is_delayed else 0.1
                    self.wasted_network_bytes += 1024 * 50 * (0.7 if is_delayed else 0.5)
                    if is_delayed:
                        # This delayed request caused deadline miss
                        pass  # already counted in delayed_requests
                else:
                    # Successfully processed within deadline
                    self.requests_processed += 1
                    self.useful_work_requests += 1
            else:
                # Still waiting to be processed
                new_pending.append((arrival_tick, deadline_ms, is_delayed, app_id))
        
        self._pending_requests = new_pending
        
        # Generate new requests every 5 ticks
        if self._req_tick % 5 != 0:
            return

        for svc in self.services:
            if not getattr(svc, "_available", False):
                continue
            app_id = getattr(getattr(svc, "application", None), "id", None)

            for _ in range(3):                           # 3 requests per batch
                self.requests_received += 1
                fault_hit = False
                is_delayed = False

                # 1) Selective service rejection
                if (not fault_hit
                        and self._fault_active(self.SELECTIVE_SERVICE_REJECTION)
                        and app_id in target_apps
                        and random.random() < rej_rate):
                    self.rejected_requests += 1
                    self.requests_failed += 1
                    self.wasted_network_bytes += 1024 * 50  # full request wasted
                    fault_hit = True

                # 2) Request dropping
                if (not fault_hit
                        and self._fault_active(self.REQUEST_DROPPING)
                        and random.random() < drop_prob):
                    self.dropped_requests += 1
                    self.requests_failed += 1
                    self.wasted_network_bytes += 1024 * 50  # full request wasted
                    self.wasted_cpu_cycles += 0.05  # minimal CPU but still waste
                    fault_hit = True

                # 3) Processing delay attack (request queued with delay)
                if (not fault_hit
                        and self._fault_active(self.PROCESSING_DELAY_ATTACK)
                        and random.random() < delay_prob):
                    self.delayed_requests += 1
                    is_delayed = True
                    # Will be processed with slowdown, may miss deadline

                # Queue request for processing (unless dropped/rejected)
                if not fault_hit or is_delayed:
                    # Assign deadline: 15-25ms (healthy ~10ms OK, delayed 30ms FAIL)
                    deadline_ms = 15 + random.random() * 10
                    self._pending_requests.append((self._req_tick, deadline_ms, is_delayed, app_id))

    def _apply_false_resource_tick(self):
        """Inflate reported CPU/RAM to mislead orchestrator."""
        # Always track actual demand (ground truth)
        self.actual_cpu_demand_history.append(self.cpu_demand)
        self.actual_ram_demand_history.append(self.memory_demand)
        
        if not self._fault_active(self.FALSE_RESOURCE_REPORTING):
            # Not doing false reporting, report truthfully
            self.reported_cpu_demand_history.append(self.cpu_demand)
            self.reported_ram_demand_history.append(self.memory_demand)
            return
        
        lie_prob  = self.fault_config.get("lie_probability", 0.25)
        inflation = self.fault_config.get("inflation_factor", 1.5)
        
        # Decide whether to lie this tick
        if random.random() < lie_prob:
            self.false_reports_count += 1
            # Report inflated resources (lie!)
            reported_cpu = self.cpu_demand * inflation
            reported_ram = self.memory_demand * inflation
        else:
            # Tell the truth this time
            reported_cpu = self.cpu_demand
            reported_ram = self.memory_demand
        
        self.reported_cpu_demand_history.append(reported_cpu)
        self.reported_ram_demand_history.append(reported_ram)

    # -- collect (written to msgpack log) ------------------------------
    def collect(self):
        metrics = super().collect()
        if not isinstance(metrics, dict):
            metrics = {}
        # Calculate average processing time
        avg_processing_time = sum(self._processing_times) / len(self._processing_times) if self._processing_times else 0
        
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
            "requests_deadline_missed": self.requests_deadline_missed,
            "avg_processing_time_ms": avg_processing_time,
            "total_faults_triggered": (
                self.delayed_requests + self.dropped_requests +
                self.rejected_requests + self.false_reports_count
            ),
        })
        return metrics


def convert_to_faulty(server, fault_type, fault_config):
    """Swap an EdgeServer instance's class to FaultyEdgeServer in-place."""
    # First upgrade to EdgeServerWithRequests if not already
    if not isinstance(server, EdgeServerWithRequests):
        server.__class__ = EdgeServerWithRequests
        # Initialize request tracking
        server.requests_received = 0
        server.requests_processed = 0
        server.requests_failed = 0
        server.requests_deadline_missed = 0
        server._req_tick = 0
        server._prev_requests_processed = 0
        server.cpu_usage_history = []
        server.ram_usage_history = []
        server.network_bytes_sent = 0
        server.network_bytes_received = 0
        server._pending_requests = []
        server._processing_times = []
        server.reported_cpu_demand_history = []
        server.reported_ram_demand_history = []
    
    # Now convert to FaultyEdgeServer
    server.__class__ = FaultyEdgeServer
    server._init_fault(fault_type, fault_config)


# ═════════════════════════════════════════════════════════════════
#  Configuration
# ═════════════════════════════════════════════════════════════════
NUM_STEPS      = 100
DUMP_INTERVAL  = 25
LAYER_DIGEST   = "sha256:aabbccdd0001"
IMAGE_DIGEST   = "sha256:aabbccdd0002"

# ── Server / fault definitions ──────────────────────────────────
SERVER_DEFS = [
    {"id": 1, "coords": [0, 0], "fault": None,                              "label": "HEALTHY"},
    {"id": 2, "coords": [2, 0], "fault": "processing_delay_attack",         "label": "DELAY"},
    {"id": 3, "coords": [4, 0], "fault": "request_dropping",                "label": "DROP"},
    {"id": 4, "coords": [6, 0], "fault": "false_resource_reporting",        "label": "FALSE-RPT"},
    {"id": 5, "coords": [0, 2], "fault": "selective_service_rejection",     "label": "REJECT"},
    {"id": 6, "coords": [2, 2], "fault": "mixed",                           "label": "MIXED"},
]

LINK_PAIRS = [(1, 2), (2, 3), (3, 4), (1, 5), (5, 6), (2, 6)]

# Fault configurations per type
FAULT_CONFIGS = {
    "processing_delay_attack": {
        "slowdown_factor": 3.0,
        "delay_probability": 0.4,
        "base_latency_ms": 10,
    },
    "request_dropping": {
        "drop_probability": 0.3,
    },
    "false_resource_reporting": {
        "lie_probability": 0.25,
        "inflation_factor": 1.5,
    },
    "selective_service_rejection": {
        "rejection_config": {
            "target_application_ids": [9, 10],   # apps on server 5
            "rejection_rate": 0.8,
        },
    },
    "mixed": {
        "slowdown_factor": 2.0,
        "delay_probability": 0.3,
        "base_latency_ms": 10,
        "drop_probability": 0.2,
        "lie_probability": 0.15,
        "inflation_factor": 1.3,
        "rejection_config": {
            "target_application_ids": [11, 12],  # apps on server 6
            "rejection_rate": 0.6,
        },
    },
}


# ═════════════════════════════════════════════════════════════════
#  Build dataset dict programmatically
# ═════════════════════════════════════════════════════════════════
def _build_dataset():
    ds = {}
    n_srv = len(SERVER_DEFS)

    # coordinate traces (static – no mobility)
    traces = {tuple(s["coords"]): [list(s["coords"])] * NUM_STEPS
              for s in SERVER_DEFS}

    # ── Network Switches ─────────────────────────────────────
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

    # ── Network Links ────────────────────────────────────────
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

    # ── Base Stations ────────────────────────────────────────
    ds["BaseStation"] = []
    for s in SERVER_DEFS:
        sid = s["id"]
        u1, u2 = sid * 2 - 1, sid * 2
        ds["BaseStation"].append({
            "attributes": {
                "id": sid, "coordinates": s["coords"], "wireless_delay": 5,
            },
            "relationships": {
                "users": [
                    {"class": "User", "id": u1},
                    {"class": "User", "id": u2},
                ],
                "edge_servers": [{"class": "EdgeServer", "id": sid}],
                "network_switch": {"class": "NetworkSwitch", "id": sid},
            },
        })

    # ── Edge Servers ─────────────────────────────────────────
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

    # ── Container Infrastructure (on server 1 only) ──────────
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

    # ── Services (2 per server → 12 total) ───────────────────
    svc_labels = ["frontend", "backend"]
    ds["Service"] = []
    for s in SERVER_DEFS:
        sid = s["id"]
        for j, lbl in enumerate(svc_labels):
            svc_id = (sid - 1) * 2 + j + 1
            cpu_d  = 1 if j == 0 else 2
            mem_d  = 512 if j == 0 else 1024
            ds["Service"].append({
                "attributes": {
                    "id": svc_id, "label": f"{lbl}-{sid}", "state": 0,
                    "_available": True, "cpu_demand": cpu_d,
                    "memory_demand": mem_d, "image_digest": IMAGE_DIGEST,
                },
                "relationships": {
                    "application": {"class": "Application", "id": svc_id},
                    "server": None,
                },
            })

    # ── Applications (1 per service → 12 total) ─────────────
    ds["Application"] = []
    for s in SERVER_DEFS:
        sid = s["id"]
        for j in range(2):
            app_id = (sid - 1) * 2 + j + 1
            ds["Application"].append({
                "attributes": {"id": app_id, "label": f"App-{app_id}"},
                "relationships": {
                    "services": [{"class": "Service", "id": app_id}],
                    "users":    [{"class": "User",    "id": app_id}],
                },
            })

    # ── Users (2 per base station → 12 total, static) ───────
    ds["User"] = []
    for s in SERVER_DEFS:
        sid = s["id"]
        coords = s["coords"]
        trace = traces[tuple(coords)]
        for j in range(2):
            uid = (sid - 1) * 2 + j + 1
            ds["User"].append({
                "attributes": {
                    "id": uid, "coordinates": list(coords),
                    "coordinates_trace": trace,
                    "delays":       {str(uid): None},
                    "delay_slas":   {str(uid): 45},
                    "communication_paths": {},
                    "making_requests": {str(uid): {"1": True}},
                },
                "relationships": {
                    "access_patterns": {
                        str(uid): {
                            "class": "CircularDurationAndIntervalAccessPattern",
                            "id": uid,
                        }
                    },
                    "mobility_model": "pathway",
                    "applications": [{"class": "Application", "id": uid}],
                    "base_station":  {"class": "BaseStation",  "id": sid},
                },
            })

    # ── Access Patterns ──────────────────────────────────────
    ds["CircularDurationAndIntervalAccessPattern"] = [
        {
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
                "app":  {"class": "Application", "id": uid},
            },
        }
        for uid in range(1, n_srv * 2 + 1)
    ]
    ds["RandomDurationAndIntervalAccessPattern"] = []
    return ds


dataset = _build_dataset()


# ═════════════════════════════════════════════════════════════════
#  Placement & stopping criterion
# ═════════════════════════════════════════════════════════════════
def targeted_placement(parameters={}):
    """Place 2 services on each server: svcs 1-2 → srv 1, 3-4 → srv 2, …"""
    servers = {s.id: s for s in EdgeServer.all()}
    for svc in Service.all():
        if svc.server is not None:
            continue
        target_sid = (svc.id - 1) // 2 + 1
        target = servers.get(target_sid)
        if target and target.has_capacity_to_host(svc):
            svc.server = target
            svc._available = True
            target.cpu_demand += svc.cpu_demand
            target.memory_demand += svc.memory_demand
            if svc not in target.services:
                target.services.append(svc)


def stopping_criterion(model):
    return model.schedule.steps >= NUM_STEPS


# ═════════════════════════════════════════════════════════════════
#  Analysis & Visualization
# ═════════════════════════════════════════════════════════════════
def analyze_simulation_results(log_dir="logs", output_dir="Analysis"):
    """Generate comprehensive charts, figures, and tables from simulation logs."""
    
    print("\n" + "=" * 78)
    print("  ANALYZING SIMULATION RESULTS")
    print("=" * 78)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load logs
    print("  Loading logs...")
    logs = {}
    log_files = {
        "EdgeServer": "EdgeServerWithRequests.msgpack",  # Healthy servers log here now
        "FaultyEdgeServer": "FaultyEdgeServer.msgpack",
        "Service": "Service.msgpack",
        "User": "User.msgpack",
    }
    
    for name, fname in log_files.items():
        fpath = os.path.join(log_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                data = msgpack.unpackb(f.read(), raw=False)
                if isinstance(data, list) and len(data) > 0:
                    logs[name] = pd.DataFrame(data)
                    print(f"    ✓ {fname}: {len(logs[name])} records")
                else:
                    logs[name] = pd.DataFrame()
        else:
            logs[name] = pd.DataFrame()
    
    has_faulty = not logs["FaultyEdgeServer"].empty
    has_healthy = not logs["EdgeServer"].empty
    
    if not has_faulty and not has_healthy:
        print("  ✗ No server logs found.")
        return
    
    # ═════════════════════════════════════════════════════════════
    # Figure 1: Fault Type Comparison
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 1: Fault Type Comparison (All Servers)...")
    
    # Combine all servers with their types
    all_servers = []
    if has_healthy:
        df_h = logs["EdgeServer"].copy()
        df_h["server_category"] = "healthy"
        all_servers.append(df_h)
    if has_faulty:
        df_f = logs["FaultyEdgeServer"].copy()
        df_f["server_category"] = df_f["fault_type"]
        all_servers.append(df_f)
    
    if all_servers:
        df_all_types = pd.concat(all_servers, ignore_index=True)
        latest_step = df_all_types["Time Step"].max()
        df_latest_types = df_all_types[df_all_types["Time Step"] == latest_step]
        
        fault_summary = df_latest_types.groupby("server_category").agg({
            "Instance ID": "count",
            "requests_received": "sum",
            "requests_processed": "sum",
            "requests_failed": "sum",
            "requests_deadline_missed": "sum",
        }).reset_index()
        
        # Add fault-specific columns (will be 0 for healthy)
        if has_faulty:
            fault_specific = df_latest_types[df_latest_types["server_category"] != "healthy"].groupby("server_category").agg({
                "delayed_requests": "sum",
                "dropped_requests": "sum",
                "rejected_requests": "sum",
                "false_reports_count": "sum",
            }).reset_index()
            fault_summary = fault_summary.merge(fault_specific, on="server_category", how="left")
            fault_summary.fillna(0, inplace=True)
        else:
            fault_summary["delayed_requests"] = 0
            fault_summary["dropped_requests"] = 0
            fault_summary["rejected_requests"] = 0
            fault_summary["false_reports_count"] = 0
        
        fault_summary.columns = ["Server Type", "Count", "Received", "Processed",
                                 "Failed", "Deadline Missed", "Delayed", "Dropped", "Rejected", "False Reports"]
        
        fig, axes = plt.subplots(3, 3, figsize=(20, 15))
        fig.suptitle("Server Type Comparison — Request & Fault Metrics (Healthy + Faulty)", fontsize=16, fontweight="bold")
        
        metrics = [
            ("Count", "Number of Servers"),
            ("Received", "Total Requests Received"),
            ("Processed", "Requests Successfully Processed"),
            ("Failed", "Requests Failed"),
            ("Deadline Missed", "Deadline Violations"),
            ("Delayed", "Delayed Requests"),
            ("Dropped", "Dropped Requests"),
            ("Rejected", "Rejected Requests"),
            ("False Reports", "False Resource Reports"),
        ]
        
        for idx, (col, title) in enumerate(metrics):
            ax = axes[idx // 3, idx % 3]
            # Use different color for healthy
            colors = []
            for st in fault_summary["Server Type"]:
                if st == "healthy":
                    colors.append("lightgreen")
                else:
                    colors.append(plt.cm.Set3((hash(st) % 256) / 256))
            
            bars = ax.bar(range(len(fault_summary)), fault_summary[col], color=colors, alpha=0.8)
            ax.set_title(title, fontweight="bold")
            ax.set_xticks(range(len(fault_summary)))
            ax.set_xticklabels(fault_summary["Server Type"], rotation=45, ha="right", fontsize=8)
            ax.grid(axis="y", alpha=0.3)
            
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        fig1_path = os.path.join(output_dir, "fig1_fault_type_comparison.png")
        plt.savefig(fig1_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Saved: {fig1_path}")
        
        table1_path = os.path.join(output_dir, "table1_fault_summary.csv")
        fault_summary.to_csv(table1_path, index=False)
        print(f"    ✓ Saved: {table1_path}")
    
    # ═════════════════════════════════════════════════════════════
    # Figure 2: Time Series — Resource Utilization
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 2: Time Series — Resource Utilization...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Time Series: Resource Utilization (Healthy vs Faulty)", fontsize=16, fontweight="bold")
    
    metrics_ts = [
        ("CPU Demand", "CPU Demand (cores)", False),
        ("RAM Demand", "Memory Demand (MB)", False),
        ("Power Consumption", "Power Consumption (W)", False),
        ("Services", "Hosted Services", True),
    ]
    
    for idx, (col, title, is_list_col) in enumerate(metrics_ts):
        ax = axes[idx // 2, idx % 2]
        
        if has_healthy and col in logs["EdgeServer"].columns:
            df_h = logs["EdgeServer"].copy()
            if is_list_col:
                df_h["_count"] = df_h[col].apply(lambda x: len(x) if isinstance(x, list) else 0)
                df_h_ts = df_h.groupby("Time Step")["_count"].mean()
            else:
                df_h_ts = df_h.groupby("Time Step")[col].mean()
            ax.plot(df_h_ts.index, df_h_ts.values, label="Healthy (avg)",
                   linewidth=2, color="green", marker="o", markersize=3, alpha=0.7)
        
        if has_faulty and col in logs["FaultyEdgeServer"].columns:
            df_f = logs["FaultyEdgeServer"].copy()
            if is_list_col:
                df_f["_count"] = df_f[col].apply(lambda x: len(x) if isinstance(x, list) else 0)
                df_f_ts = df_f.groupby("Time Step")["_count"].mean()
            else:
                df_f_ts = df_f.groupby("Time Step")[col].mean()
            ax.plot(df_f_ts.index, df_f_ts.values, label="Faulty (avg)",
                   linewidth=2, color="red", marker="s", markersize=3, alpha=0.7)
        
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Time Step")
        ax.set_ylabel(title.split("(")[1].strip(")") if "(" in title else title)
        ax.legend()
        ax.grid(alpha=0.3)
    
    plt.tight_layout()
    fig2_path = os.path.join(output_dir, "fig2_time_series_resources.png")
    plt.savefig(fig2_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig2_path}")
    
    # ═════════════════════════════════════════════════════════════
    # Figure 3: Request Processing Over Time
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 3: Request Processing Timeline (All Servers)...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Request Processing Evolution (Healthy + Faulty Servers)", fontsize=16, fontweight="bold")
    
    request_metrics = [
        ("requests_received", "Requests Received"),
        ("requests_processed", "Requests Processed"),
        ("requests_failed", "Requests Failed"),
        ("requests_deadline_missed", "Deadline Violations"),
    ]
    
    # Combine all servers
    all_servers = []
    if has_healthy:
        df_h = logs["EdgeServer"].copy()
        df_h["server_category"] = "healthy"
        all_servers.append(df_h)
    if has_faulty:
        df_f = logs["FaultyEdgeServer"].copy()
        df_f["server_category"] = df_f["fault_type"]
        all_servers.append(df_f)
    
    df_all_types = pd.concat(all_servers, ignore_index=True)
    
    for idx, (col, title) in enumerate(request_metrics):
        ax = axes[idx // 2, idx % 2]
        
        # Plot healthy first with distinct style
        if has_healthy and col in logs["EdgeServer"].columns:
            df_h = df_all_types[df_all_types["server_category"] == "healthy"]
            ts_data = df_h.groupby("Time Step")[col].sum()
            ax.plot(ts_data.index, ts_data.values, label="healthy", 
                   linewidth=3, color="green", marker="o", markersize=4, linestyle="-")
        
        # Plot each fault type
        if has_faulty:
            for ft in logs["FaultyEdgeServer"]["fault_type"].unique():
                df_ft = df_all_types[df_all_types["server_category"] == ft]
                if col in df_ft.columns:
                    ts_data = df_ft.groupby("Time Step")[col].sum()
                    ax.plot(ts_data.index, ts_data.values, label=ft, 
                           linewidth=2, marker="s", markersize=3, alpha=0.8)
        
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Time Step")
        ax.set_ylabel("Count")
        ax.legend(fontsize=8, loc="best")
        ax.grid(alpha=0.3)
    
    plt.tight_layout()
    fig3_path = os.path.join(output_dir, "fig3_request_processing_timeline.png")
    plt.savefig(fig3_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig3_path}")
    
    # ═════════════════════════════════════════════════════════════
    # Figure 4: Load Balancing Distribution
    # ═════════════════════════════════════════════════════════════
    if has_healthy or has_faulty:
        print("\n  Generating Figure 4: Load Balancing Distribution...")
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle("Load Balancing: Service Distribution & CPU Load (All Server Types)", fontsize=16, fontweight="bold")
        
        all_servers = []
        if has_healthy:
            df_h = logs["EdgeServer"].copy()
            df_h["server_category"] = "healthy"
            all_servers.append(df_h)
        if has_faulty:
            df_f = logs["FaultyEdgeServer"].copy()
            df_f["server_category"] = df_f["fault_type"]
            all_servers.append(df_f)
        
        df_all = pd.concat(all_servers, ignore_index=True)
        latest_step = df_all["Time Step"].max()
        df_latest = df_all[df_all["Time Step"] == latest_step]
        df_latest["Services_count"] = df_latest["Services"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        
        ax = axes[0]
        service_dist = df_latest.groupby("server_category")["Services_count"].sum().sort_values(ascending=False)
        # Use green for healthy, other colors for faults
        colors = []
        for st in service_dist.index:
            if st == "healthy":
                colors.append("lightgreen")
            else:
                colors.append(plt.cm.Set3((hash(st) % 256) / 256))
        
        bars = ax.bar(range(len(service_dist)), service_dist.values, color=colors, alpha=0.8)
        ax.set_title("Total Services Hosted by Server Type", fontweight="bold")
        ax.set_xticks(range(len(service_dist)))
        ax.set_xticklabels(service_dist.index, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Number of Services")
        ax.grid(axis="y", alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        ax = axes[1]
        cpu_loads = df_latest.groupby("server_category")["CPU Demand"].mean().sort_values(ascending=False)
        colors = []
        for st in cpu_loads.index:
            if st == "healthy":
                colors.append("lightgreen")
            else:
                colors.append(plt.cm.Set3((hash(st) % 256) / 256))
        
        bars = ax.bar(range(len(cpu_loads)), cpu_loads.values, color=colors, alpha=0.8)
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
        fig4_path = os.path.join(output_dir, "fig4_load_balancing.png")
        plt.savefig(fig4_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Saved: {fig4_path}")
    
    # ═════════════════════════════════════════════════════════════
    # Figure 5: Resource REPORTED vs Actual Usage (FALSE REPORTING DETECTION)
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 5: Reported Demand vs Actual Usage (False Reporting Detection)...")
    
    # Combine servers for comparison
    all_servers = []
    if has_healthy:
        df_h = logs["EdgeServer"].copy()
        df_h["server_category"] = "healthy"
        all_servers.append(df_h)
    if has_faulty:
        df_f = logs["FaultyEdgeServer"].copy()
        df_f["server_category"] = df_f["fault_type"]
        all_servers.append(df_f)
    
    df_all = pd.concat(all_servers, ignore_index=True)
    latest_step = df_all["Time Step"].max()
    df_latest = df_all[df_all["Time Step"] == latest_step]
    
    # Check if new metrics exist
    has_cpu_reported = "cpu_demand_reported" in df_latest.columns
    has_ram_reported = "ram_demand_reported" in df_latest.columns
    has_cpu_actual = "cpu_demand_actual" in df_latest.columns
    has_ram_actual = "ram_demand_actual" in df_latest.columns
    
    if (has_cpu_reported and has_cpu_actual) or (has_ram_reported and has_ram_actual):
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle("Reported Demand vs Actual Usage (False Reporting Detection)", fontsize=16, fontweight="bold")
        
        # Get all server types
        server_types = df_latest["server_category"].unique()
        server_types_sorted = sorted(server_types, key=lambda x: (x != "healthy", x))  # healthy first
        
        # CPU Reported vs Actual by Type
        ax = axes[0, 0]
        if has_cpu_reported and has_cpu_actual:
            cpu_reported = []
            cpu_actual = []
            for st in server_types_sorted:
                df_st = df_latest[df_latest["server_category"] == st]
                cpu_reported.append(df_st["cpu_demand_reported"].sum())
                cpu_actual.append(df_st["cpu_demand_actual"].sum())
            
            x = np.arange(len(server_types_sorted))
            width = 0.35
            ax.bar(x - width/2, cpu_reported, width, label="Reported (what server claims)", color="lightcoral", alpha=0.8)
            ax.bar(x + width/2, cpu_actual, width, label="Actual Demand (ground truth)", color="darkblue", alpha=0.8)
            ax.set_title("CPU: Reported vs Actual Demand", fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(server_types_sorted, rotation=45, ha="right", fontsize=9)
            ax.set_ylabel("CPU (cores)")
            ax.legend()
            ax.grid(alpha=0.3, axis="y")
        
        # RAM Reported vs Actual by Type
        ax = axes[0, 1]
        if has_ram_reported and has_ram_actual:
            ram_reported = []
            ram_actual = []
            for st in server_types_sorted:
                df_st = df_latest[df_latest["server_category"] == st]
                ram_reported.append(df_st["ram_demand_reported"].sum())
                ram_actual.append(df_st["ram_demand_actual"].sum())
            
            x = np.arange(len(server_types_sorted))
            width = 0.35
            ax.bar(x - width/2, ram_reported, width, label="Reported (what server claims)", color="lightcoral", alpha=0.8)
            ax.bar(x + width/2, ram_actual, width, label="Actual Demand (ground truth)", color="darkgreen", alpha=0.8)
            ax.set_title("RAM: Reported vs Actual Demand", fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(server_types_sorted, rotation=45, ha="right", fontsize=9)
            ax.set_ylabel("RAM (MB)")
            ax.legend()
            ax.grid(alpha=0.3, axis="y")
        
        # CPU Reporting Inflation (%) by Type
        ax = axes[1, 0]
        if has_cpu_reported and has_cpu_actual:
            cpu_inflations = []
            for st in server_types_sorted:
                df_st = df_latest[df_latest["server_category"] == st]
                reported = df_st["cpu_demand_reported"].sum()
                actual = df_st["cpu_demand_actual"].sum()
                inflation = ((reported - actual) / actual * 100) if actual > 0 else 0
                cpu_inflations.append(inflation)
            
            colors = ["green" if st == "healthy" else ("red" if "false" in st.lower() else "coral") for st in server_types_sorted]
            bars = ax.bar(range(len(server_types_sorted)), cpu_inflations, color=colors, alpha=0.7)
            ax.set_title("CPU Reporting Inflation (False > 0%)", fontweight="bold")
            ax.set_xticks(range(len(server_types_sorted)))
            ax.set_xticklabels(server_types_sorted, rotation=45, ha="right", fontsize=9)
            ax.set_ylabel("Inflation: (Reported - Actual) / Actual (%)")
            ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
            ax.grid(alpha=0.3, axis="y")
            for i, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%', ha='center', va='bottom' if height >= 0 else 'top', fontsize=8)
        
        # RAM Reporting Inflation (%) by Type
        ax = axes[1, 1]
        if has_ram_reported and has_ram_actual:
            ram_inflations = []
            for st in server_types_sorted:
                df_st = df_latest[df_latest["server_category"] == st]
                reported = df_st["ram_demand_reported"].sum()
                actual = df_st["ram_demand_actual"].sum()
                inflation = ((reported - actual) / actual * 100) if actual > 0 else 0
                ram_inflations.append(inflation)
            
            colors = ["green" if st == "healthy" else ("red" if "false" in st.lower() else "coral") for st in server_types_sorted]
            bars = ax.bar(range(len(server_types_sorted)), ram_inflations, color=colors, alpha=0.7)
            ax.set_title("RAM Reporting Inflation (False > 0%)", fontweight="bold")
            ax.set_xticks(range(len(server_types_sorted)))
            ax.set_xticklabels(server_types_sorted, rotation=45, ha="right", fontsize=9)
            ax.set_ylabel("Inflation: (Reported - Actual) / Actual (%)")
            ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
            ax.grid(alpha=0.3, axis="y")
            for i, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%', ha='center', va='bottom' if height >= 0 else 'top', fontsize=8)
        
        plt.tight_layout()
        fig5_path = os.path.join(output_dir, "fig5_reported_vs_actual.png")
        plt.savefig(fig5_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Saved: {fig5_path}")
    else:
        print("    ℹ No resource reporting metrics found, skipping Figure 5")
    
    # ═════════════════════════════════════════════════════════════
    # Figure 6: Network Traffic in Bytes (NEW)
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 6: Network Traffic Analysis (Bytes)...")
    
    has_network = "network_bytes_total" in df_latest.columns
    
    if has_network:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("Network Traffic Analysis by Server Type (Bytes)", fontsize=16, fontweight="bold")
        
        # Total traffic by server type (including healthy)
        ax = axes[0, 0]
        traffic_by_type = df_latest.groupby("server_category")["network_bytes_total"].sum() / (1024 * 1024)
        traffic_by_type = traffic_by_type.sort_values(ascending=False)
        colors_traffic = ["green" if label == "healthy" else plt.cm.Set3((hash(label) % 256) / 256) 
                         for label in traffic_by_type.index]
        bars = ax.bar(range(len(traffic_by_type)), traffic_by_type.values, color=colors_traffic, alpha=0.8)
        ax.set_title("Total Network Traffic by Server Type", fontweight="bold")
        ax.set_xticks(range(len(traffic_by_type)))
        ax.set_xticklabels(traffic_by_type.index, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Traffic (MB)")
        ax.grid(alpha=0.3, axis="y")
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}', ha='center', va='bottom', fontsize=8)
        
        # Sent vs Received (All Servers)
        ax = axes[0, 1]
        total_sent = df_latest["network_bytes_sent"].sum() / (1024 * 1024)
        total_received = df_latest["network_bytes_received"].sum() / (1024 * 1024)
        bars = ax.bar(["Sent", "Received"], [total_sent, total_received], color=["skyblue", "salmon"], alpha=0.7)
        ax.set_title("Sent vs Received (All Servers)", fontweight="bold")
        ax.set_ylabel("Traffic (MB)")
        ax.grid(alpha=0.3, axis="y")
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}', ha='center', va='bottom')
        
        # Per-server traffic (all servers, colored by type)
        ax = axes[1, 0]
        df_sorted = df_latest.sort_values("network_bytes_total", ascending=False)
        x = np.arange(len(df_sorted))
        colors_bars = ["green" if st == "healthy" else "coral" for st in df_sorted["server_category"]]
        ax.bar(x, df_sorted["network_bytes_total"] / (1024 * 1024), color=colors_bars, alpha=0.7)
        ax.set_title("Network Traffic per Server", fontweight="bold")
        ax.set_xlabel("Server (sorted by traffic)")
        ax.set_ylabel("Traffic (MB)")
        ax.grid(alpha=0.3, axis="y")
        
        # Traffic over time by server type (including healthy)
        ax = axes[1, 1]
        all_servers_ts = []
        if has_healthy:
            df_h = logs["EdgeServer"].copy()
            df_h["server_category"] = "healthy"
            all_servers_ts.append(df_h)
        if has_faulty:
            df_f = logs["FaultyEdgeServer"].copy()
            df_f["server_category"] = df_f["fault_type"]
            all_servers_ts.append(df_f)
        
        df_all_ts = pd.concat(all_servers_ts, ignore_index=True)
        
        # Plot healthy with distinct style
        if has_healthy:
            df_h_ts = df_all_ts[df_all_ts["server_category"] == "healthy"].groupby("Time Step")["network_bytes_total"].sum() / (1024 * 1024)
            ax.plot(df_h_ts.index, df_h_ts.values, label="healthy", linewidth=3, color="green", marker="o", markersize=4)
        
        # Plot each fault type
        if has_faulty:
            for ft in logs["FaultyEdgeServer"]["fault_type"].unique():
                df_ft_ts = df_all_ts[df_all_ts["server_category"] == ft].groupby("Time Step")["network_bytes_total"].sum() / (1024 * 1024)
                ax.plot(df_ft_ts.index, df_ft_ts.values, label=ft, linewidth=2, marker="s", markersize=3, alpha=0.8)
        
        ax.set_title("Network Traffic Over Time by Type", fontweight="bold")
        ax.set_xlabel("Time Step")
        ax.set_ylabel("Traffic (MB)")
        ax.legend(fontsize=8, loc="best")
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        fig6_path = os.path.join(output_dir, "fig6_network_traffic_bytes.png")
        plt.savefig(fig6_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Saved: {fig6_path}")
    else:
        print("    ℹ No network traffic metrics found, skipping Figure 6")
    
    # ═════════════════════════════════════════════════════════════
    # Table 2: Overall Summary Statistics
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Table 2: Overall Summary Statistics...")
    
    summary_stats = []
    
    # Combine all server types
    all_servers = []
    if has_healthy:
        df_h = logs["EdgeServer"].copy()
        df_h["server_category"] = "healthy"
        all_servers.append(df_h)
    if has_faulty:
        df_f = logs["FaultyEdgeServer"].copy()
        df_f["server_category"] = df_f["fault_type"]
        all_servers.append(df_f)
    
    df_all_summary = pd.concat(all_servers, ignore_index=True)
    latest_step = df_all_summary["Time Step"].max()
    df_latest_summary = df_all_summary[df_all_summary["Time Step"] == latest_step]
    df_latest_summary["Services_count"] = df_latest_summary["Services"].apply(lambda x: len(x) if isinstance(x, list) else 0)
    
    for server_type in sorted(df_latest_summary["server_category"].unique(), key=lambda x: (x != "healthy", x)):
        df_st = df_latest_summary[df_latest_summary["server_category"] == server_type]
        
        recv = df_st["requests_received"].sum() if "requests_received" in df_st.columns else 0
        proc = df_st["requests_processed"].sum() if "requests_processed" in df_st.columns else 0
        fail = df_st["requests_failed"].sum() if "requests_failed" in df_st.columns else 0
        deadline_miss = df_st["requests_deadline_missed"].sum() if "requests_deadline_missed" in df_st.columns else 0
        avg_proc_time = df_st["avg_processing_time_ms"].mean() if "avg_processing_time_ms" in df_st.columns else 0
        success_rate = (proc / recv * 100) if recv > 0 else 100.0
        deadline_met_rate = ((recv - deadline_miss) / recv * 100) if recv > 0 else 100.0
        
        summary_stats.append({
            "Server Type": server_type,
            "Count": len(df_st),
            "Avg CPU (%)": (df_st["CPU Demand"] / df_st["CPU"] * 100).mean(),
            "Avg Memory (%)": (df_st["RAM Demand"] / df_st["RAM"] * 100).mean(),
            "Avg Power (W)": df_st["Power Consumption"].mean(),
            "Total Services": df_st["Services_count"].sum(),
            "Requests Recv": recv,
            "Requests Proc": proc,
            "Requests Failed": fail,
            "Deadline Missed": deadline_miss,
            "Success Rate (%)": success_rate,
            "Deadline Met Rate (%)": deadline_met_rate,
            "Avg Proc Time (ms)": avg_proc_time,
        })
    
    df_summary = pd.DataFrame(summary_stats)
    table2_path = os.path.join(output_dir, "table2_overall_summary.csv")
    df_summary.to_csv(table2_path, index=False)
    print(f"    ✓ Saved: {table2_path}")
    print("\n  Summary Statistics:")
    print(df_summary.to_string(index=False))
    
    print("\n" + "=" * 78)
    print(f"  ANALYSIS COMPLETE — {len([f for f in os.listdir(output_dir) if f.endswith('.png')])} figures, {len([f for f in os.listdir(output_dir) if f.endswith('.csv')])} tables saved to '{output_dir}/'")
    print("=" * 78)
    
    # ═════════════════════════════════════════════════════════════
    # Figure 7: Statistical Distributions (Box Plots)
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 7: Statistical Distributions (Variability Analysis)...")
    
    # Combine all servers
    all_servers = []
    if has_healthy:
        df_h = logs["EdgeServer"].copy()
        df_h["server_category"] = "healthy"
        all_servers.append(df_h)
    if has_faulty:
        df_f = logs["FaultyEdgeServer"].copy()
        df_f["server_category"] = df_f["fault_type"]
        all_servers.append(df_f)
    
    df_all_dist = pd.concat(all_servers, ignore_index=True)
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Statistical Distributions — Variability Analysis Across Server Types", fontsize=16, fontweight="bold")
    
    # Get all server types
    server_types = sorted(df_all_dist["server_category"].unique(), key=lambda x: (x != "healthy", x))
    
    # Processing Time Distribution
    ax = axes[0, 0]
    if "avg_processing_time_ms" in df_all_dist.columns:
        data_by_type = [df_all_dist[df_all_dist["server_category"] == st]["avg_processing_time_ms"].dropna() 
                       for st in server_types]
        bp = ax.boxplot(data_by_type, labels=server_types, patch_artist=True)
        for i, (patch, st) in enumerate(zip(bp['boxes'], server_types)):
            patch.set_facecolor('lightgreen' if st == "healthy" else 'lightcoral')
        ax.set_title("Processing Time Distribution", fontweight="bold")
        ax.set_ylabel("Processing Time (ms)")
        ax.set_xticklabels(server_types, rotation=45, ha="right", fontsize=8)
        ax.grid(alpha=0.3, axis='y')
    
    # CPU Utilization Distribution
    ax = axes[0, 1]
    if "CPU Demand" in df_all_dist.columns:
        data_by_type = [(df_all_dist[df_all_dist["server_category"] == st]["CPU Demand"] / 
                        df_all_dist[df_all_dist["server_category"] == st]["CPU"] * 100).dropna() 
                       for st in server_types]
        bp = ax.boxplot(data_by_type, labels=server_types, patch_artist=True)
        for i, (patch, st) in enumerate(zip(bp['boxes'], server_types)):
            patch.set_facecolor('lightgreen' if st == "healthy" else 'lightcoral')
        ax.set_title("CPU Utilization Distribution", fontweight="bold")
        ax.set_ylabel("CPU Utilization (%)")
        ax.set_xticklabels(server_types, rotation=45, ha="right", fontsize=8)
        ax.grid(alpha=0.3, axis='y')
    
    # Success Rate Distribution
    ax = axes[1, 0]
    latest = df_all_dist[df_all_dist["Time Step"] == df_all_dist["Time Step"].max()]
    data_by_type = []
    for st in server_types:
        df_st = latest[latest["server_category"] == st]
        if "requests_received" in df_st.columns and "requests_processed" in df_st.columns:
            success_rates = (df_st["requests_processed"] / df_st["requests_received"] * 100).fillna(100)
            data_by_type.append(success_rates)
        else:
            data_by_type.append(pd.Series([100]))
    
    bp = ax.boxplot(data_by_type, labels=server_types, patch_artist=True)
    for i, (patch, st) in enumerate(zip(bp['boxes'], server_types)):
        patch.set_facecolor('lightgreen' if st == "healthy" else 'lightcoral')
    ax.set_title("Success Rate Distribution", fontweight="bold")
    ax.set_ylabel("Success Rate (%)")
    ax.set_xticklabels(server_types, rotation=45, ha="right", fontsize=8)
    ax.grid(alpha=0.3, axis='y')
    ax.set_ylim(0, 105)
    
    # Deadline Met Rate Distribution
    ax = axes[1, 1]
    data_by_type = []
    for st in server_types:
        df_st = latest[latest["server_category"] == st]
        if "requests_received" in df_st.columns and "requests_deadline_missed" in df_st.columns:
            recv = df_st["requests_received"]
            missed = df_st["requests_deadline_missed"]
            met_rates = ((recv - missed) / recv * 100).fillna(100)
            data_by_type.append(met_rates)
        else:
            data_by_type.append(pd.Series([100]))
    
    bp = ax.boxplot(data_by_type, labels=server_types, patch_artist=True)
    for i, (patch, st) in enumerate(zip(bp['boxes'], server_types)):
        patch.set_facecolor('lightgreen' if st == "healthy" else 'lightcoral')
    ax.set_title("Deadline Met Rate Distribution", fontweight="bold")
    ax.set_ylabel("Deadline Met Rate (%)")
    ax.set_xticklabels(server_types, rotation=45, ha="right", fontsize=8)
    ax.grid(alpha=0.3, axis='y')
    ax.set_ylim(0, 105)
    
    plt.tight_layout()
    fig7_path = os.path.join(output_dir, "fig7_statistical_distributions.png")
    plt.savefig(fig7_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig7_path}")
    
    # ═════════════════════════════════════════════════════════════
    # Figure 8: Impact Severity Analysis
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 8: Impact Severity Analysis...")
    
    # Calculate impact metrics vs healthy baseline
    df_latest_impact = df_all_dist[df_all_dist["Time Step"] == df_all_dist["Time Step"].max()]
    
    # Get healthy baseline (aggregate metrics for fair comparison)
    healthy_df = df_latest_impact[df_latest_impact["server_category"] == "healthy"]
    if not healthy_df.empty:
        # Use aggregate totals, not per-server averages
        h_recv = healthy_df["requests_received"].sum()
        h_proc = healthy_df["requests_processed"].sum()
        h_miss = healthy_df["requests_deadline_missed"].sum()
        h_fail = healthy_df["requests_failed"].sum()
        
        healthy_baseline = {
            "throughput": h_proc if h_proc > 0 else 1,  # total processed
            "latency": healthy_df["avg_processing_time_ms"].mean(),  # avg latency is OK to average
            "success_rate": (h_proc / h_recv * 100) if h_recv > 0 else 100,
            "deadline_met": ((h_recv - h_miss) / h_recv * 100) if h_recv > 0 else 100,
            "failure_rate": (h_fail / h_recv * 100) if h_recv > 0 else 0,
        }
    else:
        healthy_baseline = {"throughput": 1, "latency": 10, "success_rate": 100, "deadline_met": 100, "failure_rate": 0}
    
    # Calculate impact for each fault type
    impact_data = []
    for st in server_types:
        if st == "healthy":
            continue
        df_st = df_latest_impact[df_latest_impact["server_category"] == st]
        if df_st.empty:
            continue
        
        # Use aggregate totals for fair comparison (not per-server averages)
        f_recv = df_st["requests_received"].sum()
        f_proc = df_st["requests_processed"].sum()
        f_miss = df_st["requests_deadline_missed"].sum()
        f_fail = df_st["requests_failed"].sum()
        
        faulty_throughput = f_proc
        faulty_latency = df_st["avg_processing_time_ms"].mean()
        faulty_success = (f_proc / f_recv * 100) if f_recv > 0 else 100
        faulty_deadline = ((f_recv - f_miss) / f_recv * 100) if f_recv > 0 else 100
        faulty_failure = (f_fail / f_recv * 100) if f_recv > 0 else 0
        
        # Calculate impact (degradation from baseline)
        throughput_degradation = max(0, (healthy_baseline["throughput"] - faulty_throughput) / healthy_baseline["throughput"] * 100)
        latency_increase = max(0, (faulty_latency - healthy_baseline["latency"]) / healthy_baseline["latency"] * 100) if faulty_latency > 0 else 0
        success_drop = max(0, healthy_baseline["success_rate"] - faulty_success)
        deadline_drop = max(0, healthy_baseline["deadline_met"] - faulty_deadline)
        failure_increase = max(0, faulty_failure - healthy_baseline["failure_rate"])
        
        # Composite severity score (weighted by importance)
        # Throughput loss & failures are most critical, then success rate, then latency, then deadlines
        severity = (throughput_degradation * 0.25 + failure_increase * 0.25 + success_drop * 0.25 + 
                   latency_increase * 0.15 + deadline_drop * 0.10)
        
        impact_data.append({
            "Fault Type": st,
            "Throughput Degradation (%)": throughput_degradation,
            "Latency Increase (%)": latency_increase,
            "Success Rate Drop (%)": success_drop,
            "Deadline Met Drop (%)": deadline_drop,
            "Failure Rate Increase (%)": failure_increase,
            "Severity Score": severity,
        })
    
    impact_df = pd.DataFrame(impact_data)
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Impact Severity Analysis — Damage Quantification vs Healthy Baseline", fontsize=16, fontweight="bold")
    
    # Throughput Degradation
    ax = axes[0, 0]
    if not impact_df.empty:
        bars = ax.bar(range(len(impact_df)), impact_df["Throughput Degradation (%)"], color='coral', alpha=0.8)
        ax.set_title("Throughput Degradation", fontweight="bold")
        ax.set_xticks(range(len(impact_df)))
        ax.set_xticklabels(impact_df["Fault Type"], rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Degradation (%)")
        ax.grid(alpha=0.3, axis='y')
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
                   ha='center', va='bottom', fontsize=9)
    
    # Latency Increase
    ax = axes[0, 1]
    if not impact_df.empty:
        bars = ax.bar(range(len(impact_df)), impact_df["Latency Increase (%)"], color='salmon', alpha=0.8)
        ax.set_title("Latency Increase", fontweight="bold")
        ax.set_xticks(range(len(impact_df)))
        ax.set_xticklabels(impact_df["Fault Type"], rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Increase (%)")
        ax.grid(alpha=0.3, axis='y')
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
                   ha='center', va='bottom', fontsize=9)
    
    # Composite Severity Score
    ax = axes[1, 0]
    if not impact_df.empty:
        impact_df_sorted = impact_df.sort_values("Severity Score", ascending=False)
        bars = ax.barh(range(len(impact_df_sorted)), impact_df_sorted["Severity Score"], color='darkred', alpha=0.8)
        ax.set_title("Composite Severity Score (Ranked)", fontweight="bold")
        ax.set_yticks(range(len(impact_df_sorted)))
        ax.set_yticklabels(impact_df_sorted["Fault Type"], fontsize=9)
        ax.set_xlabel("Severity Score")
        ax.grid(alpha=0.3, axis='x')
        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2., f'{width:.1f}',
                   ha='left', va='center', fontsize=9, fontweight='bold')
    
    # Multi-dimensional Impact Radar
    ax = axes[1, 1]
    if not impact_df.empty and len(impact_df) > 0:
        # Select top 3 most severe faults for readability
        top_faults = impact_df.nlargest(min(3, len(impact_df)), "Severity Score")
        
        categories = ["Throughput\nDegradation", "Latency\nIncrease", "Success\nRate Drop", 
                     "Deadline\nMet Drop", "Failure Rate\nIncrease"]
        num_vars = len(categories)
        
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]
        
        ax = plt.subplot(224, projection='polar')
        
        colors_radar = plt.cm.Set2(range(len(top_faults)))
        for idx, (_, row) in enumerate(top_faults.iterrows()):
            values = [
                row["Throughput Degradation (%)"],
                row["Latency Increase (%)"],
                row["Success Rate Drop (%)"],
                row["Deadline Met Drop (%)"],
                row["Failure Rate Increase (%)"],
            ]
            values += values[:1]
            ax.plot(angles, values, 'o-', linewidth=2, label=row["Fault Type"], color=colors_radar[idx])
            ax.fill(angles, values, alpha=0.15, color=colors_radar[idx])
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=7)
        ax.set_title("Multi-Dimensional Impact", fontweight="bold", pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=8)
        ax.grid(True)
    
    plt.tight_layout()
    fig8_path = os.path.join(output_dir, "fig8_impact_severity.png")
    plt.savefig(fig8_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig8_path}")
    
    # Save impact severity table
    if not impact_df.empty:
        impact_csv_path = os.path.join(output_dir, "table3_impact_severity.csv")
        impact_df.to_csv(impact_csv_path, index=False)
        print(f"    ✓ Saved: {impact_csv_path}")
    
    # ═════════════════════════════════════════════════════════════
    # Figure 9: Resource Waste Analysis
    # ═════════════════════════════════════════════════════════════
    print("\n  Generating Figure 9: Resource Waste & Efficiency Analysis...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("Resource Waste & Efficiency Analysis", fontsize=16, fontweight="bold")
    
    # Resource Efficiency by Server Type
    ax = axes[0, 0]
    if "resource_efficiency" in df_latest_impact.columns:
        efficiency_by_type = df_latest_impact.groupby("server_category")["resource_efficiency"].mean().sort_values()
        colors_eff = ['green' if st == "healthy" else 'coral' for st in efficiency_by_type.index]
        bars = ax.barh(range(len(efficiency_by_type)), efficiency_by_type.values, color=colors_eff, alpha=0.8)
        ax.set_title("Resource Efficiency (Useful Work %)", fontweight="bold")
        ax.set_yticks(range(len(efficiency_by_type)))
        ax.set_yticklabels(efficiency_by_type.index, fontsize=9)
        ax.set_xlabel("Efficiency (%)")
        ax.set_xlim(0, 105)
        ax.grid(alpha=0.3, axis='x')
        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2., f'{width:.1f}%',
                   ha='left', va='center', fontsize=9, fontweight='bold')
    
    # Wasted Resources Comparison
    ax = axes[0, 1]
    if "wasted_cpu_cycles" in df_latest_impact.columns and "wasted_network_bytes" in df_latest_impact.columns:
        waste_by_type = df_latest_impact.groupby("server_category").agg({
            "wasted_cpu_cycles": "sum",
            "wasted_network_bytes": "sum"
        }).sort_values("wasted_cpu_cycles", ascending=False)
        
        x = np.arange(len(waste_by_type))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, waste_by_type["wasted_cpu_cycles"], width, 
                      label="Wasted CPU", color='lightcoral', alpha=0.8)
        bars2 = ax.bar(x + width/2, waste_by_type["wasted_network_bytes"] / (1024 * 1024), width,
                      label="Wasted Network (MB)", color='lightsalmon', alpha=0.8)
        
        ax.set_title("Wasted Resources by Server Type", fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(waste_by_type.index, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Wasted Resources")
        ax.legend()
        ax.grid(alpha=0.3, axis='y')
    
    # Useful Work vs Waste Stacked Bar
    ax = axes[1, 0]
    if "useful_work_requests" in df_latest_impact.columns and "requests_failed" in df_latest_impact.columns:
        work_by_type = df_latest_impact.groupby("server_category").agg({
            "useful_work_requests": "sum",
            "requests_failed": "sum"
        }).sort_values("useful_work_requests", ascending=False)
        
        x = np.arange(len(work_by_type))
        ax.bar(x, work_by_type["useful_work_requests"], label="Useful Work", color='lightgreen', alpha=0.8)
        ax.bar(x, work_by_type["requests_failed"], bottom=work_by_type["useful_work_requests"],
              label="Wasted Effort", color='lightcoral', alpha=0.8)
        
        ax.set_title("Useful Work vs Wasted Effort", fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(work_by_type.index, rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Request Count")
        ax.legend()
        ax.grid(alpha=0.3, axis='y')
    
    # Efficiency vs Load Scatter
    ax = axes[1, 1]
    if "resource_efficiency" in df_latest_impact.columns and "CPU Demand" in df_latest_impact.columns:
        for st in server_types:
            df_st = df_latest_impact[df_latest_impact["server_category"] == st]
            if not df_st.empty:
                cpu_util = (df_st["CPU Demand"] / df_st["CPU"] * 100)
                efficiency = df_st["resource_efficiency"]
                color = 'green' if st == "healthy" else plt.cm.Set3((hash(st) % 256) / 256)
                ax.scatter(cpu_util, efficiency, label=st, alpha=0.7, s=100, color=color)
        
        ax.set_title("Efficiency vs CPU Utilization", fontweight="bold")
        ax.set_xlabel("CPU Utilization (%)")
        ax.set_ylabel("Resource Efficiency (%)")
        ax.legend(fontsize=8, loc="best")
        ax.grid(alpha=0.3)
        ax.set_xlim(0, 105)
        ax.set_ylim(0, 105)
    
    plt.tight_layout()
    fig9_path = os.path.join(output_dir, "fig9_resource_waste.png")
    plt.savefig(fig9_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    ✓ Saved: {fig9_path}")
    
    print("\n" + "=" * 78)
    print(f"  ENHANCED ANALYSIS COMPLETE")
    print(f"  Total: {len([f for f in os.listdir(output_dir) if f.endswith('.png')])} figures, {len([f for f in os.listdir(output_dir) if f.endswith('.csv')])} tables")
    print("=" * 78)


# ═════════════════════════════════════════════════════════════════
#  Main
# ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":

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

    print("Loading dataset ...")
    simulator.initialize(input_file=dataset)

    # ── Convert all servers to request-tracking first ────────
    for srv in EdgeServer.all():
        if not isinstance(srv, EdgeServerWithRequests):
            srv.__class__ = EdgeServerWithRequests
            srv.requests_received = 0
            srv.requests_processed = 0
            srv.requests_failed = 0
            srv.requests_deadline_missed = 0
            srv._req_tick = 0
            srv._prev_requests_processed = 0
            srv.cpu_usage_history = []
            srv.ram_usage_history = []
            srv.network_bytes_sent = 0
            srv.network_bytes_received = 0
            srv._pending_requests = []
            srv._processing_times = []
            srv.actual_cpu_demand_history = []
            srv.actual_ram_demand_history = []
            srv.actual_cpu_demand_history = []
            srv.actual_ram_demand_history = []
            srv.reported_cpu_demand_history = []
            srv.reported_ram_demand_history = []
            srv.wasted_cpu_cycles = 0
            srv.wasted_network_bytes = 0
            srv.useful_work_requests = 0

    # ── Convert faulty servers ───────────────────────────────
    for sdef in SERVER_DEFS:
        if sdef["fault"] is None:
            continue
        srv = next(s for s in EdgeServer.all() if s.id == sdef["id"])
        convert_to_faulty(srv, sdef["fault"], FAULT_CONFIGS[sdef["fault"]])
        print(f"  Server {sdef['id']} → FaultyEdgeServer ({sdef['label']})")

    print(f"  Edge servers : {len(EdgeServer.all())}")
    print(f"  Services     : {len(Service.all())}")
    print(f"  Users        : {len(User.all())}")
    print(f"  Applications : {len(Application.all())}")

    print(f"\nRunning simulation for {NUM_STEPS} steps ...")
    simulator.run_model()

    # ═════════════════════════════════════════════════════════
    #  Results
    # ═════════════════════════════════════════════════════════
    print("\n" + "=" * 78)
    print("  SIMULATION RESULTS")
    print("=" * 78)
    print(f"  Steps completed: {simulator.schedule.steps}\n")

    # ── Edge Servers ─────────────────────────────────────────
    print("  ── Edge Servers ──")
    for server in EdgeServer.all():
        power = server.get_power_consumption()
        util  = (server.cpu_demand / server.cpu * 100) if server.cpu else 0
        faulty = isinstance(server, FaultyEdgeServer)
        tag = f" [{server.fault_type}]" if faulty else " [HEALTHY]"
        print(f"    Server {server.id} ({server.model_name}){tag}:")
        print(f"      CPU {server.cpu_demand}/{server.cpu} ({util:.0f}%)  "
              f"MEM {server.memory_demand}/{server.memory}  "
              f"Services {len(server.services)}  "
              f"Power {power:.1f} W")
        
        # Show request metrics for all servers
        if hasattr(server, 'requests_received'):
            dl_miss = getattr(server, 'requests_deadline_missed', 0)
            print(f"      Requests : recv={server.requests_received}  "
                  f"proc={server.requests_processed}  "
                  f"failed={server.requests_failed}  "
                  f"deadline_missed={dl_miss}")
        
        # Show fault details only for faulty servers
        if faulty:
            print(f"      Faults   : delayed={server.delayed_requests}  "
                  f"dropped={server.dropped_requests}  "
                  f"rejected={server.rejected_requests}  "
                  f"false_rpt={server.false_reports_count}")

    # ── Services ─────────────────────────────────────────────
    print("\n  ── Services ──")
    for svc in Service.all():
        srv = svc.server
        tag = ""
        if srv and isinstance(srv, FaultyEdgeServer):
            tag = f" ({srv.fault_type})"
        srv_id = f"{srv.id}{tag}" if srv else "—"
        print(f"    Svc {svc.id:2d} ({svc.label:15s})  → server {srv_id}")

    # ── Comparison table ─────────────────────────────────────
    print("\n  ── Fault Comparison (faulty servers vs healthy baseline) ──")
    print(f"    {'Server':>8s}  {'Type':>28s}  {'Recv':>6s}  {'Proc':>6s}  "
          f"{'Failed':>6s}  {'DL-Miss':>7s}  {'Delay':>6s}  {'Drop':>6s}  {'Reject':>6s}  "
          f"{'FalseR':>6s}  {'Power':>7s}")
    print("    " + "-" * 120)
    for server in EdgeServer.all():
        power = server.get_power_consumption()
        if isinstance(server, FaultyEdgeServer):
            dl_miss = getattr(server, 'requests_deadline_missed', 0)
            print(f"    {server.id:>8d}  {server.fault_type:>28s}  "
                  f"{server.requests_received:>6d}  "
                  f"{server.requests_processed:>6d}  "
                  f"{server.requests_failed:>6d}  "
                  f"{dl_miss:>7d}  "
                  f"{server.delayed_requests:>6d}  "
                  f"{server.dropped_requests:>6d}  "
                  f"{server.rejected_requests:>6d}  "
                  f"{server.false_reports_count:>6d}  "
                  f"{power:>7.1f}")
        else:
            # Show request metrics for healthy servers too
            recv = getattr(server, 'requests_received', 0)
            proc = getattr(server, 'requests_processed', 0)
            fail = getattr(server, 'requests_failed', 0)
            dl_miss = getattr(server, 'requests_deadline_missed', 0)
            print(f"    {server.id:>8d}  {'HEALTHY (baseline)':>28s}  "
                  f"{recv:>6d}  {proc:>6d}  {fail:>6d}  {dl_miss:>7d}  "
                  f"{'—':>6s}  {'—':>6s}  {'—':>6s}  {'—':>6s}  "
                  f"{power:>7.1f}")

    # ── Logs ─────────────────────────────────────────────────
    print("\n  ── Simulation Logs ──")
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
    
    # Run analysis
    analyze_simulation_results()
