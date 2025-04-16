import logging
import multiprocessing
import sys
from pathlib import Path

from llmse6.config import TomlConfigParser
from llmse6.mcp.aggregator_server import create_aggregator_server_from_config

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
            target=_run_server_process, args=(aggregator_server, aggregator_type)
        )
        process.start()
        logger.info(
            f"Started process PID {process.pid} for server '{aggregator_name}'."
        )


def main():
    logging.basicConfig(level=logging.INFO)
    run_mcp_aggregator()


if __name__ == "__main__":
    main()
