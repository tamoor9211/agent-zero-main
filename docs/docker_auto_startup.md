# Docker Auto-Startup Feature

Agent Zero now supports automatic Docker container startup when you run the main UI from VS Code or any other environment. This feature ensures that the core components that depend on Docker are automatically initialized without manual intervention.

## How It Works

When you run `run_ui.py`, Agent Zero will automatically:

1. **Check if Docker auto-startup is enabled** (default: enabled)
2. **Detect if running in a containerized environment** (if so, skip auto-startup)
3. **Try Docker Compose first** (recommended approach)
4. **Fall back to Python Docker API** if Docker Compose is unavailable
5. **Start the necessary containers** for code execution and other features
6. **Handle cleanup** when the application shuts down

## Configuration

### Environment Variables

You can configure Docker ports and settings using the `.env.docker` file:

```bash
# HTTP port for Agent Zero web interface
AGENT_ZERO_HTTP_PORT=55080

# SSH port for Agent Zero container access  
AGENT_ZERO_SSH_PORT=55022

# Docker image to use
AGENT_ZERO_IMAGE=frdel/agent-zero:latest
```

### Settings

Docker auto-startup is controlled by the `rfc_auto_docker` setting, which defaults to `true`. You can disable it in your settings if needed.

## Docker Compose Method (Recommended)

Agent Zero includes a `docker-compose.yml` file in the project root that defines the necessary services:

```yaml
version: '3.8'

services:
  agent-zero:
    container_name: agent-zero-dev
    image: frdel/agent-zero:latest
    volumes:
      - .:/a0
      - ./work_dir:/root
    ports:
      - "${AGENT_ZERO_HTTP_PORT:-55080}:80"
      - "${AGENT_ZERO_SSH_PORT:-55022}:22"
    environment:
      - BRANCH=development
    restart: unless-stopped
```

### Requirements for Docker Compose

- Docker installed and running
- Docker Compose installed (either `docker-compose` or `docker compose`)

## Python Docker API Method (Fallback)

If Docker Compose is not available, Agent Zero will use the Python Docker API to manage containers directly.

### Requirements for Python Docker API

- Docker installed and running
- Python `docker` package (included in requirements.txt)

## Usage

### Running from VS Code

1. Open the project in VS Code
2. Run `run_ui.py` directly (F5 or Run button)
3. Agent Zero will automatically start Docker containers
4. Access the web interface at `http://localhost:5000` (or your configured port)

### Running from Command Line

```bash
# Navigate to project directory
cd /path/to/agent-zero

# Run the UI (Docker containers will start automatically)
python run_ui.py
```

### Testing Docker Integration

You can test the Docker auto-startup functionality without running the full application:

```bash
python test_docker_startup.py
```

This will show you:
- Whether Docker auto-startup is enabled
- Docker Compose availability
- Python Docker API availability
- Configuration status

## Troubleshooting

### Docker Not Starting

1. **Check Docker is running**: Ensure Docker Desktop or Docker daemon is running
2. **Check permissions**: Make sure your user has permission to access Docker
3. **Check ports**: Ensure the configured ports (55080, 55022) are not in use
4. **Check logs**: Look at the console output for specific error messages

### NixOS Users

If you're using NixOS and encounter `docker-compose` command not found:

```bash
# Install docker-compose in your environment
nix-env -iA nixpkgs.docker-compose

# Or use docker compose (newer syntax)
docker compose version
```

### Port Conflicts

If the default ports are in use, modify `.env.docker`:

```bash
AGENT_ZERO_HTTP_PORT=56080
AGENT_ZERO_SSH_PORT=56022
```

### Disabling Auto-Startup

If you prefer to manage Docker containers manually, you can disable auto-startup by setting `rfc_auto_docker` to `false` in your Agent Zero settings.

## Manual Container Management

You can also manage containers manually:

```bash
# Start containers
docker-compose up -d

# Stop containers  
docker-compose down

# View running containers
docker-compose ps
```

## Benefits

- **Seamless Development**: No need to manually start Docker containers
- **Automatic Cleanup**: Containers are properly stopped when Agent Zero shuts down
- **Flexible Configuration**: Support for both Docker Compose and Python Docker API
- **VS Code Integration**: Works perfectly with VS Code's run/debug features
- **Error Handling**: Graceful fallbacks and informative error messages
