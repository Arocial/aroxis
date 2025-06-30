import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from kissllm.mcp import MCPConfig, SSEMCPConfig, StdioMCPConfig
from kissllm.mcp.aggregator import MCPAggregatorServer

from arox.utils.git import clone_or_update_repo

logger = logging.getLogger(__name__)


def build_backend_configs(
    aggregator_name: str,
    servers_config: Dict[str, Dict[str, Any]],
    git_clone_dir: Optional[Path] = None,
    proxy_config: Optional[Dict[str, Any]] = None,
) -> List[MCPConfig]:
    """
    Builds a list of MCPConfig objects for aggregator backends from configuration data.

    Handles git source cloning/updating (with optional proxy) and config generation for stdio/sse types.
    """
    backend_configs: List[MCPConfig] = []

    for backend_name, backend_conf in servers_config.items():
        logger.info(
            f"Processing backend '{backend_name}' for aggregator '{aggregator_name}'..."
        )
        backend_type = backend_conf.get("type", "stdio")
        git_src = backend_conf.get("git_src")
        git_rev = backend_conf.get("git_rev")  # Optional revision
        use_proxy = backend_conf.get(
            "use_proxy", False
        )  # Check if proxy should be used for this repo
        repo_path: Optional[Path] = None
        effective_proxy_config = proxy_config if use_proxy else None

        # Handle git source if specified
        if git_src:
            try:
                logger.info(
                    f"Attempting to clone/update '{git_src}' for backend '{backend_name}'. Proxy enabled: {use_proxy}"
                )
                repo_path = clone_or_update_repo(
                    git_url=git_src,
                    git_rev=git_rev,
                    target_base_dir=git_clone_dir,
                    proxy_config=effective_proxy_config,  # Pass proxy config if needed
                )
                logger.info(
                    f"Using repository path '{repo_path}' for backend '{backend_name}'. Proxy used: {use_proxy}"
                )
            except Exception as e:
                logger.error(
                    f"Skipping backend '{backend_name}' due to git error for source '{git_src}': {e}",
                    exc_info=True,
                )
                continue  # Skip this backend if git fails

        # Build config based on type
        try:
            if backend_type == "stdio":
                command = backend_conf.get("command")
                args = backend_conf.get("args", [])
                cwd = backend_conf.get("cwd")  # Optional working directory

                if not command:
                    logger.warning(
                        f"Skipping stdio backend '{backend_name}': 'command' is missing."
                    )
                    continue

                # If cwd is specified, resolve it relative to the repo_path if git_src was used
                if cwd and repo_path:
                    effective_cwd = repo_path / Path(cwd)
                elif repo_path:
                    effective_cwd = (
                        repo_path  # Default to repo root if cwd not specified
                    )
                else:
                    effective_cwd = (
                        Path(cwd) if cwd else None
                    )  # Use specified cwd or None

                if effective_cwd and not effective_cwd.is_dir():
                    logger.warning(
                        f"Specified 'cwd' ('{effective_cwd}') for stdio backend '{backend_name}' does not exist or is not a directory. Using default."
                    )
                    effective_cwd = (
                        repo_path  # Fallback to repo path if specified cwd is invalid
                    )

                env = os.environ.copy()
                if effective_cwd:
                    env["PWD"] = str(effective_cwd)
                config = StdioMCPConfig(
                    name=backend_name,
                    command=command,
                    args=args,
                    env=env,
                )
                logger.debug(
                    f"Created StdioMCPConfig for backend '{backend_name}' with cwd='{effective_cwd}'."
                )

            elif backend_type == "sse":
                url = backend_conf.get("url")
                if not url:
                    logger.warning(
                        f"Skipping sse backend '{backend_name}': 'url' is missing."
                    )
                    continue
                config = SSEMCPConfig(
                    name=backend_name,
                    url=url,
                    # Add other SSEMCPConfig params if needed (headers, etc.)
                )
                logger.debug(f"Created SSEMCPConfig for backend '{backend_name}'.")

            else:
                logger.warning(
                    f"Skipping backend '{backend_name}': Unsupported type '{backend_type}'."
                )
                continue

            backend_configs.append(config)
            logger.info(f"Successfully configured backend '{backend_name}'.")

        except Exception as e:
            logger.error(
                f"Failed to create MCPConfig for backend '{backend_name}', skipping: {e}",
                exc_info=True,
            )
            continue

    return backend_configs


def create_aggregator_server_from_config(
    aggregator_name: str,
    aggregator_config: Dict[str, Any],
    global_config: Dict[str, Any],  # Pass the global config to access proxy settings
    git_clone_dir: Optional[Path] = None,
) -> MCPAggregatorServer:
    """
    Creates an MCPAggregatorServer instance from its configuration dictionary.
    Reads global proxy settings if available.
    """
    logger.info(f"Creating MCP Aggregator Server '{aggregator_name}'...")

    servers_config = aggregator_config.get("servers")
    if not servers_config or not isinstance(servers_config, dict):
        raise ValueError(
            f"Aggregator configuration for '{aggregator_name}' is missing or invalid 'servers' table."
        )

    # Extract proxy config from global settings
    proxy_config = global_config.get("network_proxy")
    if proxy_config and proxy_config.get("host"):
        logger.info(
            f"Global network proxy configured: {proxy_config['protocol']}://{proxy_config['host']}:{proxy_config.get('port')}"
        )
    else:
        logger.info(
            "No global network proxy configured or configuration is incomplete."
        )
        proxy_config = None  # Ensure it's None if incomplete

    backend_configs = build_backend_configs(
        aggregator_name, servers_config, git_clone_dir, proxy_config
    )

    if not backend_configs:
        raise ValueError(
            f"No valid backend servers could be configured for aggregator '{aggregator_name}'."
        )

    # Extract aggregator-specific settings (e.g., host, port for SSE mode)
    aggregator_settings = {
        k: v for k, v in aggregator_config.items() if k not in ["type", "servers"]
    }

    aggregator = MCPAggregatorServer(
        backend_configs=backend_configs, name=aggregator_name, **aggregator_settings
    )
    logger.info(
        f"MCP Aggregator Server '{aggregator_name}' created successfully with {len(backend_configs)} backend(s)."
    )
    return aggregator
