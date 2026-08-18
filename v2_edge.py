import random
from edge_sim_py.components.edge_server import EdgeServer


class FaultyEdgeServer(EdgeServer):
    PROCESSING_DELAY_ATTACK = "processing_delay_attack"
    REQUEST_DROPPING = "request_dropping"
    FALSE_RESOURCE_REPORTING = "false_resource_reporting"
    SELECTIVE_SERVICE_REJECTION = "selective_service_rejection"
    
    def __init__(self, *args, fault_type=None, fault_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fault_type = fault_type
        self.fault_config = fault_config or {}
        
        # Fault-specific metrics - these accumulate over simulation
        self.dropped_requests = 0
        self.rejected_requests = 0
        self.false_reports_count = 0
        self.delayed_requests = 0
        
        # Power consumption model: idle + active power
        self.power_profile = {
            'idle_power': 20,  # Watts at idle
            'peak_power': 200,  # Watts at 100% CPU
        }
        self.power_consumption = 0  # Current power draw
        
        # Request processing metrics
        self.requests_received = 0
        self.requests_processed = 0
        self.requests_failed = 0
        
        # Track initialization
        self._fault_initialized = True

    def calculate_power_consumption(self):
        """Calculate power consumption based on CPU utilization."""
        idle = self.power_profile['idle_power']
        peak = self.power_profile['peak_power']
        
        # Get CPU utilization percentage
        if self.cpu > 0:
            utilization = (self.cpu_demand / self.cpu) if hasattr(self, 'cpu_demand') else 0
            utilization = min(1.0, max(0.0, utilization))
        else:
            utilization = 0
        
        # Linear power model: P = idle + (peak - idle) * utilization
        self.power_consumption = idle + (peak - idle) * utilization
        return self.power_consumption

    def process_requests(self):
        """Process requests from services, applying Byzantine faults.
        
        Only process every Nth timestep to avoid excessive computation.
        """
        if not hasattr(self, 'services') or not self.services:
            return
        
        # Only process requests every 10 timesteps to reduce computational overhead
        if not hasattr(self, '_request_step_counter'):
            self._request_step_counter = 0
        
        self._request_step_counter += 1
        if self._request_step_counter % 10 != 0:
            return
        
        # Each service processes ~5 requests per 10 timestep interval
        requests_per_service = 5
        
        for service in self.services:
            if not hasattr(service, '_available') or not service._available:
                continue
            
            # Generate requests for this service
            for _ in range(requests_per_service):
                self.requests_received += 1
                
                # Apply Byzantine faults (only apply drop/reject randomly)
                if random.random() < 0.1:  # Only 10% of requests trigger faults
                    dropped = self._apply_request_dropping()
                    rejected = self._apply_selective_service_rejection(service)
                    
                    if dropped or rejected:
                        self.requests_failed += 1
                    else:
                        # Request processed successfully
                        self.requests_processed += 1
                        if hasattr(service, 'requests_processed'):
                            service.requests_processed += 1
                else:
                    # Normal request processing
                    self.requests_processed += 1
                    if hasattr(service, 'requests_processed'):
                        service.requests_processed += 1

    def _apply_processing_delay_attack(self, delay):
        slowdown_factor = self.fault_config.get('slowdown_factor', 2.0)
        return delay * slowdown_factor

    def _apply_request_dropping(self):
        """Apply request dropping fault if configured."""
        if self.fault_type != self.REQUEST_DROPPING and 'mixed' not in (self.fault_type or ''):
            return False
        
        drop_probability = self.fault_config.get('drop_probability', 0.3)
        if random.random() < drop_probability:
            self.dropped_requests += 1
            return True
        return False

    def _apply_false_resource_reporting(self, cpu_value):
        """Apply false resource reporting fault if configured."""
        if self.fault_type != self.FALSE_RESOURCE_REPORTING and 'mixed' not in (self.fault_type or ''):
            return cpu_value
        
        lie_probability = self.fault_config.get('lie_probability', 0.25)
        inflation_factor = self.fault_config.get('inflation_factor', 1.5)
        
        if random.random() < lie_probability:
            self.false_reports_count += 1
            return cpu_value * inflation_factor
        return cpu_value

    def _apply_selective_service_rejection(self, service):
        """Apply selective service rejection fault if configured."""
        if self.fault_type != self.SELECTIVE_SERVICE_REJECTION and 'mixed' not in (self.fault_type or ''):
            return False
        
        rejection_config = self.fault_config.get('rejection_config', {})
        target_apps = rejection_config.get('target_application_ids', [])
        rejection_rate = rejection_config.get('rejection_rate', 0.8)
        
        if not target_apps:
            return False
        
        try:
            app_id = None
            
            if hasattr(service, 'application_id'):
                app_id = service.application_id
            elif hasattr(service, 'application'):
                if hasattr(service.application, 'id'):
                    app_id = service.application.id
                elif isinstance(service.application, int):
                    app_id = service.application
            
            if app_id and app_id in target_apps:
                if random.random() < rejection_rate:
                    self.rejected_requests += 1
                    return True
        except Exception as e:
            pass
        
        return False

    def step(self):
        """Execute one step of the simulation.
        
        Override of EdgeServer.step() to add Byzantine fault and power calculations.
        """
        try:
            # Calculate power consumption based on current CPU utilization
            self.calculate_power_consumption()
            
            # Process requests with Byzantine faults (throttled for performance)
            self.process_requests()
        except Exception as e:
            # Don't let metrics calculation break the simulation
            pass
        
        # Call parent step method
        try:
            super().step()
        except Exception as e:
            pass

    def get_processing_delay(self, service):
        """Get processing delay, applying attack if configured.
        
        Override of EdgeServer method.
        """
        # Get base delay from parent
        delay = 100  # Default fallback
        
        try:
            # Safely call parent method
            delay = super().get_processing_delay(service)
        except AttributeError:
            # Parent doesn't have this method, use fallback
            if service:
                delay = getattr(service, 'cpu_demand', 100) * 0.1
            else:
                delay = 100
        except Exception as e:
            # Any other error, use fallback
            delay = 100
        
        # Apply delay attack if configured
        if self.fault_type == self.PROCESSING_DELAY_ATTACK or 'mixed' in self.fault_type:
            self.delayed_requests += 1
            return self._apply_processing_delay_attack(delay)
        
        return delay

    def can_process_service(self, service):
        """Check if server can process service, applying faults as needed.
        
        Override of EdgeServer method.
        """
        # Apply selective service rejection first
        if self.fault_type == self.SELECTIVE_SERVICE_REJECTION or 'mixed' in self.fault_type:
            if self._apply_selective_service_rejection(service):
                return False
        
        # Apply request dropping
        if self.fault_type == self.REQUEST_DROPPING or 'mixed' in self.fault_type:
            if self._apply_request_dropping():
                return False
        
        # Check parent's capacity constraints
        try:
            return super().can_process_service(service)
        except Exception:
            # If parent method fails, assume capacity exists
            return True

    def get_available_cpu(self):
        """Get available CPU, with false reporting if configured.
        
        Override of EdgeServer method.
        """
        cpu = 8000  # Default fallback
        
        try:
            # Safely call parent method
            cpu = super().get_available_cpu()
        except AttributeError:
            # Parent doesn't have this method
            if hasattr(self, 'cpu_available'):
                cpu = self.cpu_available
            elif hasattr(self, 'cpu'):
                cpu = getattr(self, 'cpu', 8000)
        except Exception:
            # Any other error, use fallback
            pass
        
        # Apply false resource reporting if configured
        if self.fault_type == self.FALSE_RESOURCE_REPORTING or 'mixed' in self.fault_type:
            return self._apply_false_resource_reporting(cpu)
        
        return cpu

    def collect(self):
        """Collect all metrics about this server.
        
        Override of EdgeServer method - IMPORTANT: call parent first!
        """
        # Get parent metrics first - this is critical!
        try:
            parent_metrics = super().collect()
        except Exception:
            # If parent collect fails, start with empty dict
            parent_metrics = {}
        
        # Ensure parent_metrics is a dict
        if not isinstance(parent_metrics, dict):
            parent_metrics = {}
        
        # Add power and request processing metrics
        perf_metrics = {
            "power_consumption": self.power_consumption,
            "requests_received": self.requests_received,
            "requests_processed": self.requests_processed,
            "requests_failed": self.requests_failed,
        }
        
        # Add fault-specific metrics
        fault_metrics = {
            "fault_type": self.fault_type,
            "is_faulty": self.fault_type is not None,
            "dropped_requests": self.dropped_requests,
            "rejected_requests": self.rejected_requests,
            "false_reports_count": self.false_reports_count,
            "delayed_requests": self.delayed_requests,
            "total_faults_triggered": (
                self.dropped_requests + self.rejected_requests + 
                self.false_reports_count + self.delayed_requests
            ),
        }
        
        # Merge metrics (parent < perf < fault, so fault takes precedence)
        parent_metrics.update(perf_metrics)
        parent_metrics.update(fault_metrics)
        
        return parent_metrics
