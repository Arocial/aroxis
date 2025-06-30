import logging
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from urllib.parse import urlparse

import git

logger = logging.getLogger(__name__)

# Default directory to store cloned repositories
DEFAULT_CLONE_DIR = Path.home() / ".cache" / "arox" / "mcp_clones"


def get_repo_name_from_url(url: str) -> str:
    """Extracts a repository name from a Git URL."""
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip("/").split("/")
    if len(path_parts) > 0:
        repo_name = path_parts[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        return repo_name
    raise ValueError(f"Could not determine repository name from URL: {url}")


@contextmanager
def git_proxy_env(
    proxy_config: Optional[Dict[str, Any]],
) -> Generator[None, None, None]:
    """Temporarily sets proxy environment variables for git operations."""
    old_env = {}
    proxy_vars = {}

    if (
        proxy_config
        and all(k in proxy_config for k in ["protocol", "host", "port"])
        and proxy_config["host"]
    ):
        protocol = proxy_config["protocol"]
        host = proxy_config["host"]
        port = proxy_config["port"]
        proxy_url = f"{protocol}://{host}:{port}" if port else f"{protocol}://{host}"

        # Determine which environment variables to set
        # Git typically uses HTTPS for github clones. SOCKS proxy often needs ALL_PROXY.
        # HTTP_PROXY and HTTPS_PROXY are standard.
        if protocol and protocol.startswith("http"):
            proxy_vars["HTTP_PROXY"] = proxy_url
            proxy_vars["HTTPS_PROXY"] = proxy_url
        elif protocol and protocol.startswith("socks"):
            proxy_vars["ALL_PROXY"] = proxy_url
            # Some tools might still need HTTP/HTTPS proxy vars set even for SOCKS
            proxy_vars["HTTP_PROXY"] = proxy_url
            proxy_vars["HTTPS_PROXY"] = proxy_url
        else:
            logger.warning(
                f"Unsupported proxy protocol: {protocol}. Not setting proxy environment variables."
            )

    # Set environment variables
    for key, value in proxy_vars.items():
        old_env[key] = os.environ.get(key)
        os.environ[key] = value
        logger.debug(f"Temporarily set environment variable: {key}={value}")

    try:
        yield
    finally:
        # Restore original environment variables
        for key, value in old_env.items():
            if value is None:
                if key in os.environ:
                    del os.environ[key]
                    logger.debug(f"Temporarily unset environment variable: {key}")
            else:
                os.environ[key] = value
                logger.debug(f"Restored environment variable: {key}={value}")
        # Also unset any vars that were newly set
        for key in proxy_vars:
            if key not in old_env and key in os.environ:
                del os.environ[key]
                logger.debug(f"Temporarily unset environment variable: {key}")


def clone_or_update_repo(
    git_url: str,
    git_rev: Optional[str] = None,
    target_base_dir: Optional[Path] = None,
    proxy_config: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Clones a git repository if it doesn't exist locally, or updates it if it does.
    Checks out a specific revision if provided. Uses proxy settings if provided.

    Args:
        git_url: The URL of the git repository.
        git_rev: The specific commit hash, tag, or branch to check out. Defaults to the default branch.
        target_base_dir: The base directory where the repository should be cloned.
                         Defaults to DEFAULT_CLONE_DIR.

    Returns:
        The local path to the cloned repository.

    Raises:
        ValueError: If the git URL is invalid or the repository name cannot be determined.
        RuntimeError: If git commands fail.
        ImportError: If gitpython is not installed.
    """
    if target_base_dir is None:
        target_base_dir = DEFAULT_CLONE_DIR

    repo_name = get_repo_name_from_url(git_url)
    repo_path = target_base_dir / repo_name

    try:
        if repo_path.exists():
            logger.info(
                f"Repository '{repo_name}' found locally at {repo_path}. Fetching updates..."
            )
            repo = git.Repo(repo_path)
            # Fetch updates from all remotes
            for remote in repo.remotes:
                try:
                    # Fetch needs proxy too
                    with git_proxy_env(proxy_config):
                        remote.fetch()
                    logger.debug(f"Fetched updates from remote '{remote.name}'.")
                except git.GitCommandError as e:
                    logger.warning(f"Could not fetch from remote '{remote.name}': {e}")
            logger.info(f"Finished fetching updates for '{repo_name}'.")

        else:
            logger.info(f"Cloning repository '{git_url}' into {repo_path}...")
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            # Clone needs proxy
            with git_proxy_env(proxy_config):
                repo = git.Repo.clone_from(git_url, repo_path)
            logger.info(f"Successfully cloned '{repo_name}'.")

        # Checkout the specified revision if provided
        if git_rev:
            logger.info(f"Checking out revision '{git_rev}' for '{repo_name}'...")
            try:
                # Checkout itself doesn't usually need network, but pull does
                repo.git.checkout(git_rev)
                # Attempt to pull if it's a branch to ensure it's up-to-date
                # This might fail if git_rev is a tag or commit hash, which is fine.
                try:
                    # Pull needs proxy
                    with git_proxy_env(proxy_config):
                        repo.git.pull()
                    logger.info(f"Pulled latest changes for '{git_rev}'.")
                except git.GitCommandError as e:
                    # Ignore errors like "You are in 'detached HEAD' state" or if not on a branch
                    logger.debug(
                        f"Note: Could not pull changes for '{git_rev}' (may be a tag/commit or offline): {e}"
                    )

                logger.info(f"Successfully checked out '{git_rev}'.")
            except git.GitCommandError as e:
                logger.error(f"Failed to checkout revision '{git_rev}': {e}")
                raise RuntimeError(
                    f"Failed to checkout revision '{git_rev}': {e}"
                ) from e

        # Ensure submodules are initialized and updated
        logger.info(f"Updating submodules for '{repo_name}'...")
        try:
            # Submodule update needs proxy
            with git_proxy_env(proxy_config):
                # Use subprocess for more control and better error reporting than gitpython's submodule handling
                subprocess.run(
                    ["git", "submodule", "update", "--init", "--recursive"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            logger.info(f"Successfully updated submodules for '{repo_name}'.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update submodules for '{repo_name}': {e.stderr}")
            raise RuntimeError(
                f"Failed to update submodules for '{repo_name}': {e}"
            ) from e
        except FileNotFoundError:
            logger.error(
                "Git command not found. Make sure git is installed and in your PATH."
            )
            raise

        return repo_path

    except git.GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        raise RuntimeError(f"Git command failed: {e}") from e
    except Exception as e:
        logger.error(f"An unexpected error occurred during git operation: {e}")
        raise


if __name__ == "__main__":
    # Example usage for testing
    logging.basicConfig(level=logging.INFO)
    # Example proxy config (replace with actual values if testing)
    # test_proxy = {"protocol": "socks5", "host": "127.0.0.1", "port": 1080}
    test_proxy = None  # Set to a dict like above to test proxy functionality
    # test_url = "https://github.com/pallets/flask.git"
    # test_rev = "3.0.0" # Example tag
    test_url = "https://github.com/jae-jae/fetcher-mcp.git"
    test_rev = None  # Default branch
    try:
        # Pass proxy_config here
        path = clone_or_update_repo(test_url, git_rev=test_rev, proxy_config=test_proxy)
        print(f"Repository available at: {path}")
        print(f"Contents: {os.listdir(path)}")

        # Example with a specific rev (e.g., a commit hash or tag)
        # path_rev = clone_or_update_repo(test_url, git_rev="specific_tag_or_commit", proxy_config=test_proxy)
        # print(f"Repository (specific rev) available at: {path_rev}")

    except (ImportError, ValueError, RuntimeError) as e:
        print(f"Error: {e}")
