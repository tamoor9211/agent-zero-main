import os
import subprocess


class DockerComposeManager:
    def __init__(self, compose_file_path: str = "docker-compose.yml"):
        # Get absolute path relative to current working directory
        if not os.path.isabs(compose_file_path):
            self.compose_file_path = os.path.abspath(compose_file_path)
        else:
            self.compose_file_path = compose_file_path
        self.compose_dir = os.path.dirname(self.compose_file_path)
        self.env_file_path = os.path.abspath(".env.docker")
        
    def is_docker_compose_available(self) -> bool:
        """Check if docker-compose or docker compose is available"""
        try:
            # Try docker compose (newer syntax)
            result = subprocess.run(
                ["docker", "compose", "version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        try:
            # Try docker-compose (older syntax)
            result = subprocess.run(
                ["docker-compose", "version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        return False
    
    def get_compose_command(self) -> list[str]:
        """Get the appropriate docker compose command"""
        try:
            # Try docker compose (newer syntax)
            result = subprocess.run(
                ["docker", "compose", "version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if result.returncode == 0:
                return ["docker", "compose"]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        # Fall back to docker-compose
        return ["docker-compose"]
    
    def start_services(self) -> bool:
        """Start Docker Compose services"""
        if not os.path.exists(self.compose_file_path):
            print(f"ERROR: Docker Compose file not found: {self.compose_file_path}")
            return False

        if not self.is_docker_compose_available():
            print("ERROR: Docker Compose is not available. Please install Docker Compose.")
            return False

        try:
            print("Starting Docker Compose services...")

            compose_cmd = self.get_compose_command()
            cmd = compose_cmd + ["-f", self.compose_file_path]

            # Add environment file if it exists
            if os.path.exists(self.env_file_path):
                cmd.extend(["--env-file", self.env_file_path])

            cmd.extend(["up", "-d"])

            result = subprocess.run(
                cmd,
                cwd=self.compose_dir,
                capture_output=True,
                text=True,
                timeout=120  # 2 minutes timeout
            )

            if result.returncode == 0:
                print("Docker Compose services started successfully!")
                return True
            else:
                print(f"ERROR: Failed to start Docker Compose services: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print("ERROR: Docker Compose startup timed out after 2 minutes")
            return False
        except Exception as e:
            print(f"ERROR: Error starting Docker Compose services: {e}")
            return False
    
    def stop_services(self) -> bool:
        """Stop Docker Compose services"""
        if not os.path.exists(self.compose_file_path):
            return True  # Nothing to stop
            
        if not self.is_docker_compose_available():
            return True  # Can't stop if compose not available
            
        try:
            print("Stopping Docker Compose services...")

            compose_cmd = self.get_compose_command()
            cmd = compose_cmd + ["-f", self.compose_file_path]

            # Add environment file if it exists
            if os.path.exists(self.env_file_path):
                cmd.extend(["--env-file", self.env_file_path])

            cmd.extend(["down"])

            result = subprocess.run(
                cmd,
                cwd=self.compose_dir,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )

            if result.returncode == 0:
                print("Docker Compose services stopped successfully!")
                return True
            else:
                print(f"ERROR: Failed to stop Docker Compose services: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print("ERROR: Docker Compose shutdown timed out after 1 minute")
            return False
        except Exception as e:
            print(f"ERROR: Error stopping Docker Compose services: {e}")
            return False
    
    def is_running(self) -> bool:
        """Check if Docker Compose services are running"""
        if not os.path.exists(self.compose_file_path):
            return False
            
        if not self.is_docker_compose_available():
            return False
            
        try:
            compose_cmd = self.get_compose_command()
            cmd = compose_cmd + ["-f", self.compose_file_path]

            # Add environment file if it exists
            if os.path.exists(self.env_file_path):
                cmd.extend(["--env-file", self.env_file_path])

            cmd.extend(["ps", "-q"])
            
            result = subprocess.run(
                cmd,
                cwd=self.compose_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # If there are running containers, ps -q will return container IDs
            return result.returncode == 0 and bool(result.stdout.strip())
            
        except Exception:
            return False
