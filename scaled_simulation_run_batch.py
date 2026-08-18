import os
import sys
import subprocess
from pathlib import Path
import time

CONFIGS = [
    # 1. Small scale, low faults - baseline
    {"servers": 100, "faulty": 10, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 100},
    
    # 2. Small scale, high faults - stress test
    {"servers": 100, "faulty": 50, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 100},
    
    # 3. Medium scale, moderate faults
    {"servers": 150, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    
    # 4. Medium-large scale, low faults
    {"servers": 200, "faulty": 20, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    
    # 5. Medium-large scale, high faults
    {"servers": 200, "faulty": 40, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    
    # 6. Large scale, moderate faults
    {"servers": 250, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    
    # 7. Very large scale, low faults
    {"servers": 300, "faulty": 10, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    
    # 8. Very large scale, high faults
    {"servers": 300, "faulty": 50, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    
    # 9. Massive scale, moderate faults
    {"servers": 400, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    
    # 10. Maximum scale, high workload
    {"servers": 500, "faulty": 20, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
     "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    
    # # 100 servers - additional
    # {"servers": 100, "faulty": 20, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 100, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 200},
    # {"servers": 100, "faulty": 40, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 100, "faulty": 20, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 100, "faulty": 30, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 200},
    # {"servers": 100, "faulty": 40, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 150},
    # {"servers": 100, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 100, "faulty": 10, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 100},
    # {"servers": 100, "faulty": 25, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 100, "faulty": 15, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 100, "faulty": 45, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    
    # # 150 servers - additional
    # {"servers": 150, "faulty": 10, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 150},
    # {"servers": 150, "faulty": 20, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 150, "faulty": 40, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 150},
    # {"servers": 150, "faulty": 50, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 150, "faulty": 20, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 150, "faulty": 30, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 150, "faulty": 40, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 150, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 150, "faulty": 10, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 2, "steps": 150},
    # {"servers": 150, "faulty": 35, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 150, "faulty": 25, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 150, "faulty": 45, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    
    # # 200 servers - additional
    # {"servers": 200, "faulty": 10, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 200, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 200, "faulty": 50, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 200, "faulty": 20, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 250},
    # {"servers": 200, "faulty": 30, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 200, "faulty": 40, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 200},
    # {"servers": 200, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 250},
    # {"servers": 200, "faulty": 10, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 200, "faulty": 25, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 200, "faulty": 35, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 200, "faulty": 15, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    
    # # 250 servers - additional
    # {"servers": 250, "faulty": 10, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 250, "faulty": 20, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 250, "faulty": 40, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 200},
    # {"servers": 250, "faulty": 50, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 250, "faulty": 20, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 250},
    # {"servers": 250, "faulty": 30, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 250, "faulty": 40, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 250, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 200},
    # {"servers": 250, "faulty": 10, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 3, "steps": 250},
    # {"servers": 250, "faulty": 35, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 250, "faulty": 15, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 250, "faulty": 45, "users_min": 3, "users_max": 5, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    
    # # 300 servers - additional
    # {"servers": 300, "faulty": 20, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 40, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 20, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 300, "faulty": 30, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 40, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 300, "faulty": 10, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 25, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 35, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 300, "faulty": 15, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    
    # # 400 servers - additional
    # {"servers": 400, "faulty": 10, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 400, "faulty": 20, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 400, "faulty": 40, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 400, "faulty": 50, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 400, "faulty": 20, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 400, "faulty": 30, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 400, "faulty": 40, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 400, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 400, "faulty": 10, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 250},
    # {"servers": 400, "faulty": 35, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 400, "faulty": 25, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 400, "faulty": 45, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    
    # # 500 servers - additional
    # {"servers": 500, "faulty": 10, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 40, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 50, "users_min": 2, "users_max": 4, "services_min": 2, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 30, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 40, "users_min": 3, "users_max": 4, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 30, "users_min": 2, "users_max": 3, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 10, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 25, "users_min": 3, "users_max": 4, "services_min": 3, "services_max": 4, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 35, "users_min": 3, "users_max": 5, "services_min": 3, "services_max": 5, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
    # {"servers": 500, "faulty": 15, "users_min": 3, "users_max": 5, "services_min": 2, "services_max": 3, 
    #  "deadline_min": 15, "deadline_max": 25, "slowdown_min": 3.0, "slowdown_max": 5.0, "grid": 4, "steps": 300},
]

def run_single_simulation(sim_num, config, total):
    script_path = Path(__file__).parent / "scaled_simulation.py"
    
    cmd = [
        sys.executable,
        str(script_path),
        "--servers", str(config["servers"]),
        "--faulty", str(config["faulty"]),
        "--users-min", str(config["users_min"]),
        "--users-max", str(config["users_max"]),
        "--services-min", str(config["services_min"]),
        "--services-max", str(config["services_max"]),
        "--deadline-min", str(config["deadline_min"]),
        "--deadline-max", str(config["deadline_max"]),
        "--slowdown-min", str(config["slowdown_min"]),
        "--slowdown-max", str(config["slowdown_max"]),
        "--grid", str(config["grid"]),
        "--steps", str(config["steps"]),
        "--dump", "25",
        "--seed", "42",
    ]
    
    print("\n" + "="*80)
    print(f"SIMULATION {sim_num}/{total}")
    print(f"  Servers: {config['servers']} | Faulty: {config['faulty']}% | "
          f"Users: {config['users_min']}-{config['users_max']} | "
          f"Services: {config['services_min']}-{config['services_max']}")
    print(f"  Deadline: {config['deadline_min']}-{config['deadline_max']} | "
          f"Slowdown: {config['slowdown_min']}-{config['slowdown_max']}x | "
          f"Grid: {config['grid']} | Steps: {config['steps']}")
    print("="*80 + "\n")
    
    try:
        start_time = time.time()
        
        result = subprocess.run(cmd, timeout=7200)
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n{'='*80}")
            print(f"SIMULATION {sim_num}/{total} COMPLETED SUCCESSFULLY in {elapsed:.1f}s")
            print(f"{'='*80}\n")
            return True
        else:
            print(f"\n{'='*80}")
            print(f"SIMULATION {sim_num}/{total} FAILED (exit code {result.returncode}) after {elapsed:.1f}s")
            print(f"{'='*80}\n")
            return False
        
    except subprocess.TimeoutExpired:
        print(f"\n{'='*80}")
        print(f"SIMULATION {sim_num}/{total} TIMEOUT (>2h)")
        print(f"{'='*80}\n")
        return False
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"SIMULATION {sim_num}/{total} ERROR: {str(e)}")
        print(f"{'='*80}\n")
        return False

def main():
    print("="*80)
    print(f"REPRESENTATIVE BATCH SIMULATION RUNNER - {len(CONFIGS)} SIMULATIONS")
    print(f"Server ranges: 100-500 | Fault rates: 10-50%")
    print(f"Randomized parameters per server:")
    print(f"  - Users: 2-5 per server (varies by config)")
    print(f"  - Services: 2-5 per server (varies by config)")
    print(f"  - Deadline: 15-25 time units (triggers violations)")
    print(f"  - Slowdown: 3.0-5.0x (triggers delay attacks)")
    print(f"Mode: SEQUENTIAL (running one at a time with full output)")
    print("="*80)
    
    print(f"\nTotal simulations: {len(CONFIGS)}")
    
    response = input(f"\nStart batch? (y/n): ")
    if response.lower() != 'y':
        print("Aborted.")
        return
    
    start_time = time.time()
    successful = 0
    failed = 0
    
    # Run sequentially
    for i, config in enumerate(CONFIGS, start=1):
        success = run_single_simulation(i, config, len(CONFIGS))
        if success:
            successful += 1
        else:
            failed += 1
        
        # Show progress
        elapsed = time.time() - start_time
        avg_time = elapsed / i
        remaining = (len(CONFIGS) - i) * avg_time
        
        print(f"Progress: {i}/{len(CONFIGS)} | Success: {successful} | Failed: {failed}")
        print(f"Elapsed: {elapsed/60:.1f}min | Est. remaining: {remaining/60:.1f}min")
        print("-"*80 + "\n")
    
    total_time = time.time() - start_time
    
    print("\n" + "="*80)
    print("BATCH COMPLETE")
    print("="*80)
    print(f"Total: {len(CONFIGS)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)")
    print(f"Average: {total_time/len(CONFIGS):.1f}s per simulation")
    print("="*80)

if __name__ == "__main__":
    main()
