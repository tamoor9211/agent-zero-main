import os
import secrets
import sys
import time
import socket
import struct
from functools import wraps
import threading
import signal
from typing import override
from flask import Flask, request, Response, session
from flask_basicauth import BasicAuth
import initialize
from python.helpers import errors, files, git, mcp_server
from python.helpers.files import get_abs_path
from python.helpers import runtime, dotenv, process
from python.helpers.extract_tools import load_classes_from_folder
from python.helpers.api import ApiHandler
from python.helpers.print_style import PrintStyle


# Set the new timezone to 'UTC'
os.environ["TZ"] = "UTC"
# Apply the timezone change
time.tzset()

# initialize the internal Flask server
webapp = Flask("app", static_folder=get_abs_path("./webui"), static_url_path="/")
webapp.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
webapp.config.update(
    JSON_SORT_KEYS=False,
    SESSION_COOKIE_SAMESITE="Strict",
)


lock = threading.Lock()

# Set up basic authentication for UI and API but not MCP
basic_auth = BasicAuth(webapp)


def is_loopback_address(address):
    loopback_checker = {
        socket.AF_INET: lambda x: struct.unpack("!I", socket.inet_aton(x))[0]
        >> (32 - 8)
        == 127,
        socket.AF_INET6: lambda x: x == "::1",
    }
    address_type = "hostname"
    try:
        socket.inet_pton(socket.AF_INET6, address)
        address_type = "ipv6"
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET, address)
            address_type = "ipv4"
        except socket.error:
            address_type = "hostname"

    if address_type == "ipv4":
        return loopback_checker[socket.AF_INET](address)
    elif address_type == "ipv6":
        return loopback_checker[socket.AF_INET6](address)
    else:
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                r = socket.getaddrinfo(address, None, family, socket.SOCK_STREAM)
            except socket.gaierror:
                return False
            for family, _, _, _, sockaddr in r:
                if not loopback_checker[family](sockaddr[0]):
                    return False
        return True


def requires_api_key(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        valid_api_key = dotenv.get_dotenv_value("API_KEY")
        if api_key := request.headers.get("X-API-KEY"):
            if api_key != valid_api_key:
                return Response("API key required", 401)
        elif request.json and request.json.get("api_key"):
            api_key = request.json.get("api_key")
            if api_key != valid_api_key:
                return Response("API key required", 401)
        else:
            return Response("API key required", 401)
        return await f(*args, **kwargs)

    return decorated


# allow only loopback addresses
def requires_loopback(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        if not is_loopback_address(request.remote_addr):
            return Response(
                "Access denied.",
                403,
                {},
            )
        return await f(*args, **kwargs)

    return decorated


# require authentication for handlers
def requires_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        user = dotenv.get_dotenv_value("AUTH_LOGIN")
        password = dotenv.get_dotenv_value("AUTH_PASSWORD")
        if user and password:
            auth = request.authorization
            if not auth or not (auth.username == user and auth.password == password):
                return Response(
                    "Could not verify your access level for that URL.\n"
                    "You have to login with proper credentials",
                    401,
                    {"WWW-Authenticate": 'Basic realm="Login Required"'},
                )
        return await f(*args, **kwargs)

    return decorated


def csrf_protect(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = session.get("csrf_token")
        header = request.headers.get("X-CSRF-Token")
        if not token or not header or token != header:
            return Response("CSRF token missing or invalid", 403)
        return await f(*args, **kwargs)

    return decorated


# handle default address, load index
@webapp.route("/", methods=["GET"])
@requires_auth
async def serve_index():
    gitinfo = None
    try:
        gitinfo = git.get_git_info()
    except Exception:
        gitinfo = {
            "version": "unknown",
            "commit_time": "unknown",
        }
    return files.read_file(
        "./webui/index.html",
        version_no=gitinfo["version"],
        version_time=gitinfo["commit_time"],
    )


def run():
    PrintStyle().print("Initializing framework...")

    # Setup cleanup handler for Docker containers
    def cleanup_handler(signum, frame):
        _ = signum, frame  # Suppress unused parameter warnings
        PrintStyle().print("Shutting down...")

        # Cleanup Docker Compose services
        if hasattr(runtime, 'compose_manager') and runtime.compose_manager:
            PrintStyle().print("Stopping Docker Compose services...")
            runtime.compose_manager.stop_services()

        # Cleanup individual Docker containers
        if hasattr(runtime, 'dockerman') and runtime.dockerman:
            PrintStyle().print("Stopping Docker container...")
            runtime.dockerman.cleanup_container()

        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)

    # Suppress only request logs but keep the startup messages
    from werkzeug.serving import WSGIRequestHandler
    from werkzeug.serving import make_server
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from a2wsgi import ASGIMiddleware

    PrintStyle().print("Starting server...")

    class NoRequestLoggingWSGIRequestHandler(WSGIRequestHandler):
        def log_request(self, code="-", size="-"):
            _ = code, size  # Suppress unused parameter warnings
            pass  # Override to suppress request logging

    # Get configuration from environment
    port = runtime.get_web_ui_port()
    host = (
        runtime.get_arg("host") or dotenv.get_dotenv_value("WEB_UI_HOST") or "localhost"
    )
    server = None

    def register_api_handler(app, handler: type[ApiHandler]):
        name = handler.__module__.split(".")[-1]
        instance = handler(app, lock)

        async def handler_wrap():
            return await instance.handle_request(request=request)

        if handler.requires_loopback():
            handler_wrap = requires_loopback(handler_wrap)
        if handler.requires_auth():
            handler_wrap = requires_auth(handler_wrap)
        if handler.requires_api_key():
            handler_wrap = requires_api_key(handler_wrap)
        if handler.requires_csrf():
            handler_wrap = csrf_protect(handler_wrap)

        app.add_url_rule(
            f"/{name}",
            f"/{name}",
            handler_wrap,
            methods=handler.get_methods(),
        )

    # initialize and register API handlers
    handlers = load_classes_from_folder("python/api", "*.py", ApiHandler)
    for handler in handlers:
        register_api_handler(webapp, handler)

    # add the webapp and mcp to the app
    app = DispatcherMiddleware(
        webapp,
        {
            "/mcp": ASGIMiddleware(app=mcp_server.DynamicMcpProxy.get_instance()),  # type: ignore
        },
    )
    PrintStyle().debug("Registered middleware for MCP and MCP token")

    PrintStyle().debug(f"Starting server at {host}:{port}...")

    server = make_server(
        host=host,
        port=port,
        app=app,
        request_handler=NoRequestLoggingWSGIRequestHandler,
        threaded=True,
    )
    process.set_server(server)
    server.log_startup()

    # Start Docker containers before initializing Agent Zero
    start_docker_if_needed()

    # Start init_a0 in a background thread when server starts
    # threading.Thread(target=init_a0, daemon=True).start()
    init_a0()

    # run the server
    server.serve_forever()


def show_docker_progress():
    """Show Docker download/startup progress in a separate thread"""
    import time

    try:
        import docker
        client = docker.from_env()
        image_name = "frdel/agent-zero-run:development"

        PrintStyle().print("Checking Docker image status...")

        # Check if image already exists
        try:
            client.images.get(image_name)
            PrintStyle().print("✓ Docker image already exists, starting container...")
            return
        except Exception:  # Catch any exception instead of specific docker.errors.ImageNotFound
            PrintStyle().print(f"Docker image '{image_name}' not found locally, downloading...")
            PrintStyle().print("⚠️  This is a large download (~3-4 GB), please be patient...")

        # Monitor download progress
        start_time = time.time()
        last_status = ""

        while True:
            try:
                # Check if image exists now
                client.images.get(image_name)
                elapsed = int(time.time() - start_time)
                PrintStyle().print(f"✓ Docker image download completed! (took {elapsed//60}m {elapsed%60}s)")
                break
            except Exception:  # Catch any exception
                # Show progress indicator
                elapsed = int(time.time() - start_time)
                status = f"⏳ Downloading Docker image... {elapsed//60}m {elapsed%60}s elapsed"
                if status != last_status:
                    PrintStyle().print(status)
                    last_status = status
                time.sleep(10)  # Check every 10 seconds

    except Exception as e:
        PrintStyle().error(f"Error monitoring Docker progress: {e}")


def start_docker_if_needed():
    """Start Docker containers if auto-docker is enabled and not running in dockerized mode"""
    try:
        from python.helpers import settings
        current_settings = settings.get_settings()

        if current_settings["rfc_auto_docker"] and not runtime.is_dockerized():
            PrintStyle().print("Auto-starting Docker containers...")

            # Show progress in background thread
            progress_thread = threading.Thread(target=show_docker_progress, daemon=True)
            progress_thread.start()

            # Try Docker Compose first
            try:
                from python.helpers.docker_compose import DockerComposeManager
                compose_manager = DockerComposeManager()

                if compose_manager.is_docker_compose_available() and not compose_manager.is_running():
                    PrintStyle().print("Starting Docker services using Docker Compose...")
                    PrintStyle().print("📥 If this is the first time, Docker will download a large image (~3-4 GB)")
                    PrintStyle().print("⏱️  Expected time with 1 MB/s internet: 50-70 minutes")

                    if compose_manager.start_services():
                        runtime.compose_manager = compose_manager
                        PrintStyle().print("✅ Docker Compose services are ready!")
                        return
                    else:
                        raise Exception("Docker Compose startup failed")
                elif compose_manager.is_running():
                    PrintStyle().print("✅ Docker Compose services are already running!")
                    runtime.compose_manager = compose_manager
                    return
                else:
                    raise Exception("Docker Compose not available")

            except Exception as compose_error:
                PrintStyle().print(f"Docker Compose unavailable ({compose_error}), trying Python Docker API...")

                # Fallback to Python Docker API
                from python.helpers import docker, log, settings

                # Get runtime config for ports
                ssh_conf = settings.get_runtime_config(current_settings)

                PrintStyle().print("Starting Docker container for code execution...")
                PrintStyle().print("📥 If this is the first time, Docker will download a large image (~3-4 GB)")
                PrintStyle().print("⏱️  Expected time with 1 MB/s internet: 50-70 minutes")

                dman = docker.DockerContainerManager(
                    logger=log.Log(),
                    name=f"A0-dev-{ssh_conf['code_exec_ssh_port']}-{ssh_conf['code_exec_http_port']}",
                    image="frdel/agent-zero-run:development",
                    ports={"22/tcp": ssh_conf["code_exec_ssh_port"], "80/tcp": ssh_conf["code_exec_http_port"]},
                    volumes={
                        os.getcwd(): {"bind": "/a0", "mode": "rw"},
                        os.path.join(os.getcwd(), "work_dir"): {"bind": "/root", "mode": "rw"},
                    },
                )
                dman.start_container()

                # Store docker manager for cleanup
                runtime.dockerman = dman
                PrintStyle().print("✅ Docker container is ready!")

    except Exception as e:
        PrintStyle().error(f"Failed to start Docker containers: {e}")
        PrintStyle().print("Continuing without Docker auto-startup...")


def init_a0():
    # initialize contexts and MCP
    init_chats = initialize.initialize_chats()
    initialize.initialize_mcp()
    # start job loop
    initialize.initialize_job_loop()

    # only wait for init chats, otherwise they would seem to dissapear for a while on restart
    init_chats.result_sync()


# run the internal server
if __name__ == "__main__":
    runtime.initialize()
    dotenv.load_dotenv()
    run()
