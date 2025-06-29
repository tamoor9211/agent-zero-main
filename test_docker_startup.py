#!/usr/bin/env python3
"""
Test script to verify Docker auto-startup functionality.
This script simulates what happens when run_ui.py starts up.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.helpers.print_style import PrintStyle
from python.helpers import runtime, dotenv, settings

def test_docker_startup():
    """Test the Docker startup functionality"""
    PrintStyle().print("Testing Docker auto-startup functionality...")
    
    # Initialize runtime
    runtime.initialize()
    dotenv.load_dotenv()
    
    # Get current settings
    current_settings = settings.get_settings()
    
    PrintStyle().print(f"RFC Auto Docker enabled: {current_settings['rfc_auto_docker']}")
    PrintStyle().print(f"Is dockerized: {runtime.is_dockerized()}")
    
    if current_settings['rfc_auto_docker'] and not runtime.is_dockerized():
        PrintStyle().print("Docker auto-startup should be triggered...")
        
        # Test Docker Compose availability
        try:
            from python.helpers.docker_compose import DockerComposeManager
            compose_manager = DockerComposeManager()
            
            PrintStyle().print(f"Docker Compose available: {compose_manager.is_docker_compose_available()}")
            PrintStyle().print(f"Docker Compose command: {' '.join(compose_manager.get_compose_command())}")
            PrintStyle().print(f"Compose file exists: {os.path.exists(compose_manager.compose_file_path)}")
            PrintStyle().print(f"Compose file path: {compose_manager.compose_file_path}")
            
            if compose_manager.is_docker_compose_available():
                PrintStyle().print("✓ Docker Compose is ready for use")
            else:
                PrintStyle().print("✗ Docker Compose is not available")
                
        except Exception as e:
            PrintStyle().error(f"Error testing Docker Compose: {e}")
            
        # Test Python Docker API availability
        try:
            from python.helpers.docker import DockerContainerManager
            PrintStyle().print("✓ Python Docker API is available")
        except Exception as e:
            PrintStyle().error(f"Error testing Python Docker API: {e}")
            
    else:
        PrintStyle().print("Docker auto-startup is disabled or running in dockerized mode")
    
    PrintStyle().print("Test completed!")

if __name__ == "__main__":
    test_docker_startup()
