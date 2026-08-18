import random
from edge_sim_py.components.edge_server import EdgeServer


class FaultyEdgeServer(EdgeServer):
    # Fault type constants
    PROCESSING_DELAY_ATTACK = "processing_delay_attack"
    REQUEST_DROPPING = "request_dropping"
    FALSE_RESOURCE_REPORTING = "false_resource_reporting"
    SELECTIVE_SERVICE_REJECTION = "selective_service_rejection"
    
    def __init__(self, *args, fault_type=None, fault_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fault_type = fault_type
        self.fault_config = fault_config or {}
        
        # Fault-specific metrics
        self.dropped_requests = 0
        self.rejected_requests = 0
        self.false_reports_count = 0
        self.delayed_requests = 0

    def _apply_processing_delay_attack(self, delay):
        slowdown_factor = self.fault_config.get('slowdown_factor', 2.0)
        return delay * slowdown_factor

    def _apply_request_dropping(self):
        drop_probability = self.fault_config.get('drop_probability', 0.3)
        if random.random() < drop_probability:
            self.dropped_requests += 1
            return True
        return False

    def _apply_false_resource_reporting(self, cpu_value):
        lie_probability = self.fault_config.get('lie_probability', 0.25)
        inflation_factor = self.fault_config.get('inflation_factor', 1.5)
        
        if random.random() < lie_probability:
            self.false_reports_count += 1
            return cpu_value * inflation_factor
        return cpu_value

    def _apply_selective_service_rejection(self, service):
        rejection_config = self.fault_config.get('rejection_config', {})
        target_apps = rejection_config.get('target_application_ids', [])
        rejection_rate = rejection_config.get('rejection_rate', 0.8)
        
        # Check if service belongs to a target application
        if hasattr(service, 'application') and service.application:
            if service.application.id in target_apps:
                if random.random() < rejection_rate:
                    self.rejected_requests += 1
                    return True
        return False

    def get_processing_delay(self, service):
        delay = 100  # Default fallback delay
        
        try:
            if hasattr(super(), 'get_processing_delay'):
                delay = super().get_processing_delay(service)
        except Exception:
            delay = getattr(service, 'cpu_demand', 100) * 0.1 if service else 100
        
        if self.fault_type == self.PROCESSING_DELAY_ATTACK:
            self.delayed_requests += 1
            return self._apply_processing_delay_attack(delay)
        
        return delay

    def can_process_service(self, service):
        if self.fault_type == self.SELECTIVE_SERVICE_REJECTION:
            if self._apply_selective_service_rejection(service):
                return False
        
        if self.fault_type == self.REQUEST_DROPPING:
            if self._apply_request_dropping():
                return False
        
        try:
            return super().can_process_service(service)
        except Exception:
            return True

    def get_available_cpu(self):
        cpu = 8000 
        
        try:
            cpu = super().get_available_cpu()
        except Exception:
            if hasattr(self, 'cpu_available'):
                cpu = self.cpu_available
            elif hasattr(self, 'cpu'):
                cpu = getattr(self, 'cpu', 8000)
        
        if self.fault_type == self.FALSE_RESOURCE_REPORTING:
            return self._apply_false_resource_reporting(cpu)
        
        return cpu

    def collect(self):
        return {
            "fault_type": self.fault_type,
            "dropped_requests": self.dropped_requests,
            "rejected_requests": self.rejected_requests,
            "false_reports_count": self.false_reports_count,
            "delayed_requests": self.delayed_requests,
        }
