import random
import math
from typing import Tuple


def random_waypoint_mobility(user) -> None:
    """
    Random waypoint mobility model for User agents in EdgeSimPy.

    simulator = Simulator(
        user_defined_functions=[random_waypoint_mobility]
    )
    
    dataset:
        "relationships": {"mobility_model": "random_waypoint_mobility"}
    """
    try:
        if not hasattr(user, 'coordinates'):
            return
        
        # Get configuration - these should be set on the user object
        # or we use sensible defaults
        bounds = getattr(user, '_mobility_bounds', (0, 0, 10000, 10000))
        boundary_handling = getattr(user, '_boundary_handling', 'bounce')
        speed = getattr(user, 'mobility_speed', 1.0)
        
        # Get current coordinates as mutable list
        current_coords = list(user.coordinates)
        
        # Generate random direction (uniform angle distribution)
        angle = random.uniform(0, 2 * math.pi)
        dx = math.cos(angle)
        dy = math.sin(angle)
        
        # Calculate new position
        new_x = current_coords[0] + dx * speed
        new_y = current_coords[1] + dy * speed
        
        # Extract bounds
        x_min, y_min, x_max, y_max = bounds
        
        # Apply boundary handling strategy
        if boundary_handling == "bounce":
            # Reflect off boundaries
            if new_x < x_min or new_x > x_max:
                dx = -dx
                new_x = current_coords[0] + dx * speed
            if new_y < y_min or new_y > y_max:
                dy = -dy
                new_y = current_coords[1] + dy * speed
        
        elif boundary_handling == "wrap":
            # Wrap around (toroidal topology)
            new_x = x_min + (new_x - x_min) % (x_max - x_min)
            new_y = y_min + (new_y - y_min) % (y_max - y_min)
        
        elif boundary_handling == "stop":
            # Stop at boundary (clamp)
            new_x = max(x_min, min(x_max, new_x))
            new_y = max(y_min, min(y_max, new_y))
        
        else:
            # Default to bounce if unknown strategy
            if new_x < x_min or new_x > x_max:
                dx = -dx
                new_x = current_coords[0] + dx * speed
            if new_y < y_min or new_y > y_max:
                dy = -dy
                new_y = current_coords[1] + dy * speed
        
        # Update user coordinates
        user.coordinates = [new_x, new_y]
        
        # Optionally record trace for analysis (if user supports it)
        try:
            if hasattr(user, 'coordinates_trace') and isinstance(user.coordinates_trace, list):
                user.coordinates_trace.append([new_x, new_y])
        except Exception:
            # Silently ignore if trace recording fails
            pass
    
    except Exception as e:
        # Silent failure - don't crash the simulation
        # In production, you might want to log this
        pass


def circular_mobility(user) -> None:
    """
    Circular mobility model - users move in circles.
    """
    try:
        if not hasattr(user, 'coordinates'):
            return
        
        # Get user-specific mobility parameters
        center_x = getattr(user, '_center_x', 5000)
        center_y = getattr(user, '_center_y', 5000)
        radius = getattr(user, '_radius', 1000)
        angular_speed = getattr(user, '_angular_speed', 0.01)
        
        # Get current angle (store on user if not present)
        if not hasattr(user, '_current_angle'):
            user._current_angle = 0
        
        # Update angle
        user._current_angle += angular_speed
        
        # Calculate new position on circle
        new_x = center_x + radius * math.cos(user._current_angle)
        new_y = center_y + radius * math.sin(user._current_angle)
        
        # Update user coordinates
        user.coordinates = [new_x, new_y]
        
    except Exception:
        pass


def stationary_user(user) -> None:
    """
    Stationary user model - users don't move.
    """
    pass

AVAILABLE_MOBILITY_MODELS = {
    'random_waypoint_mobility': random_waypoint_mobility,
    'circular_mobility': circular_mobility,
    'stationary_user': stationary_user,
}
