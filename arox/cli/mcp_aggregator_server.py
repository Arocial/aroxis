import logging
import multiprocessing
import sys
import time
from pathlib import Path

from arox.config import TomlConfigParser
from arox.mcp.aggregator_server import create_aggregator_server_from_config

logger = logging.getLogger(__name__)


def _run_server_process(server, server_type):
    """Target function to run a server in a separate process."""
    try:
        server.run(server_type)
    except Exception as e:
        logger.error(
            f"Error running server '{server.name}' in process: {e}", exc_info=True
        )


def run_mcp_aggregator():
    """Loads config, creates, and runs MCP Aggregator servers in separate processes."""

    # --- Configuration Loading ---
    config_parser = TomlConfigParser()
    config_parser.add_argument(
        "workspace", default="./workspace", help="Workspace directory"
    )
    config_parser.add_argument_group(
        "aggregator_mcp_servers", help="Aggregator MCP servers", expose_raw=True
    )

    config = config_parser.parse_args()

    aggregator_configs = config.aggregator_mcp_servers
    git_clone_dir = Path(config.workspace) / "backend_mcp_servers"

    if not aggregator_configs:
        logger.error(
            "No MCP aggregator configurations found under [aggregator_mcp_servers] in the config file(s)."
        )
        sys.exit(1)

    # List to keep track of process info (process object, server obj, server type)
    processes_info = []
    for aggregator_name, aggregator_config in aggregator_configs.items():
        aggregator_type = aggregator_config.get("type", "stdio").lower()

        aggregator_server = create_aggregator_server_from_config(
            aggregator_name=aggregator_name,
            aggregator_config=aggregator_config,
            global_config=config,  # Pass the entire parsed config object
            git_clone_dir=git_clone_dir,
        )
        logger.info(
            f"Starting MCP Aggregator server '{aggregator_name}' in '{aggregator_type}' mode..."
        )
        if aggregator_type == "sse":
            aggregator_server.settings.port = aggregator_config.get("port", "7070")
            aggregator_server.settings.host = aggregator_config.get("host", "localhost")

        # Run each server in a separate process
        process = multiprocessing.Process(
            target=_run_server_process,
            args=(aggregator_server, aggregator_type),
            daemon=True,  # Set daemon=True so child exits when parent exits
        )
        process.start()
        logger.info(
            f"Started process PID {process.pid} for server '{aggregator_name}'."
        )
        # Store process and its restart info
        processes_info.append(
            {
                "process": process,
                "server": aggregator_server,
                "type": aggregator_type,
                "name": aggregator_name,  # Store name for logging
            }
        )
        # Removed extra parenthesis here

    # Keep the main process alive, monitor children, and handle cleanup
    try:
        while True:
            for i, proc_info in enumerate(processes_info):
                process = proc_info["process"]
                if not process.is_alive():
                    server_name = proc_info["name"]
                    server_obj = proc_info["server"]
                    server_type = proc_info["type"]
                    logger.warning(
                        f"Process PID {process.pid} (Server: {server_name}) exited unexpectedly with code {process.exitcode}. Relaunching..."
                    )

                    # Relaunch the process
                    new_process = multiprocessing.Process(
                        target=_run_server_process,
                        args=(server_obj, server_type),
                        daemon=True,
                    )
                    new_process.start()
                    logger.info(
                        f"Relaunched server '{server_name}' as new process PID {new_process.pid}."
                    )
                    # Update the list with the new process info
                    processes_info[i]["process"] = new_process

            time.sleep(5)  # Check periodically
    except KeyboardInterrupt:
        logger.info("Received interrupt signal (Ctrl+C). Shutting down...")
    finally:
        logger.info("Shutting down aggregator servers...")
        # with this bug: https://github.com/modelcontextprotocol/python-sdk/issues/514,
        # the sse server processes don't shutdown as expected.
        # As a workaround, we wait for a period and force kill processes.
        for proc_info in processes_info:
            process = proc_info["process"]
            if process.is_alive():
                logger.info(
                    f"Terminating process PID {process.pid} (Server: {proc_info['name']})..."
                )
                process.terminate()

        # Wait for processes to terminate
        shutdown_timeout = 5  # seconds
        start_time = time.time()
        while time.time() - start_time < shutdown_timeout:
            all_terminated = True
            for proc_info in processes_info:
                if proc_info["process"].is_alive():
                    all_terminated = False
                    break
            if all_terminated:
                break
            time.sleep(0.1)

        # Force kill any remaining processes
        for proc_info in processes_info:
            process = proc_info["process"]
            if process.is_alive():
                logger.warning(
                    f"Process PID {process.pid} (Server: {proc_info['name']}) did not terminate gracefully. Forcing kill..."
                )
                process.kill()
                process.join()  # Ensure the process is cleaned up

        logger.info("All aggregator servers shut down.")


def main():
    logging.basicConfig(level=logging.INFO)
    run_mcp_aggregator()


if __name__ == "__main__":
    main()
