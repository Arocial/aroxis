import os
from pathlib import Path

import configargparse
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent


def get_config():
    # Parse command line arguments and config
    parser = configargparse.ArgParser(
        default_config_files=["config.yaml"],
        description="Product Manager Agent Configuration",
        config_file_parser_class=configargparse.YAMLConfigFileParser,
    )
    parser.add_argument("-c", "--config", is_config_file=True, help="config file path")
    parser.add_argument(
        "--model",
        default="deepseek/deepseek-chat",
        help="Model to use with ChatLiteLLM",
    )
    parser.add_argument(
        "--workspace",
        default="workspace",
        help="Path for agents to work, default to $current_dir/workspace",
    )

    # Observability configuration group
    obs_group = parser.add_argument_group("Observability Configuration")
    obs_group.add_argument(
        "--observability",
        choices=["langfuse", None],
        default=None,
        help="Observability provider to use (default: None)",
    )
    obs_group.add_argument(
        "--langfuse_public_key",
        env_var="LANGFUSE_PUBLIC_KEY",
        help="Langfuse public key",
    )
    obs_group.add_argument(
        "--langfuse_secret_key",
        env_var="LANGFUSE_SECRET_KEY",
        help="Langfuse secret key",
    )
    obs_group.add_argument(
        "--langfuse_host", env_var="LANGFUSE_HOST", help="Langfuse host URL"
    )

    # API Keys group
    api_group = parser.add_argument_group("API Keys")
    api_group.add_argument(
        "--api-key",
        action="append",
        help="Set API key in format provider=<key>. Example: --api-key deepseek=<key>",
    )
    api_group.add_argument(
        "--set-env",
        action="append",
        default=[],
        help="Set environment variables in format NAME=value. "
        "Example: --set-env AWS_REGION=us-west-2 (can be used multiple times)",
    )

    # Agent configuration group
    agent_group = parser.add_argument_group("Agent Configuration")
    agent_group.add_argument(
        "--agent_metadata",
        type=yaml.safe_load,
        default={},
        help="YAML string with agent-specific metadata overrides",
    )
    args = parser.parse_args()

    # Set environment variables from config
    os.environ["LANGFUSE_PUBLIC_KEY"] = args.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = args.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = args.langfuse_host

    # Process arbitrary API keys
    if args.api_key:
        for key_spec in args.api_key:
            try:
                provider, key = key_spec.split("=", 1)
                provider = provider.upper()
                os.environ[f"{provider}_API_KEY"] = key
            except ValueError:
                print(
                    f"Warning: Invalid API key format: {key_spec}. Expected provider=<key>"
                )

    # Process environment variables
    if args.set_env:
        for env_spec in args.set_env:
            try:
                var_name, value = env_spec.split("=", 1)
                os.environ[var_name] = value
            except ValueError:
                print(
                    f"Warning: Invalid env format: {env_spec}. Expected VAR_NAME=value"
                )

    # Ensure workspace directory exists
    workspace_path = Path(args.workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)

    add_extra_config(args)
    return args


def add_extra_config(config):
    config.user_path = Path.home() / ".llmse6"
    config.user_path.mkdir(parents=True, exist_ok=True)

    config.verbose_out_path = config.user_path / "__verbose_out__"
    config.verbose_out_path.mkdir(parents=True, exist_ok=True)

    config.agent_metadata_path = PROJECT_ROOT / "agents" / "metadata"
