from pathlib import Path
from typing import Any, Dict, List, Optional

import tomli

from llmse6.utils import deep_merge


class TomlConfigParser:
    def __init__(self, config_files: Optional[List[Path]] = None):
        self._raw_data = None
        self.known_groups = []
        self.defaults = {}
        self.parsed = Config({})
        self.default_group_name = "DEFAULT"
        self.default_group = self.add_argument_group(self.default_group_name)
        self.config_files = config_files

    def parse_args(self):
        self.load_config()
        for group in self.known_groups:
            group.parse_args()
        self.parsed.update(self.parsed.pop(self.default_group_name))
        return self.parsed

    def add_argument_group(self, name: str, help="", expose_raw=False):
        """Create an argument group for organizing related arguments in TOML tables

        Args:
            name: The name of the group (will be a TOML table name)

        Returns:
            ArgumentGroup: A group object that can have arguments added to it
        """
        group = ArgumentGroup(self, name, help, expose_raw)
        self.known_groups.append(group)
        return group

    def add_argument(
        self, name: str, default=None, help: str = "", required: bool = False
    ):
        """Add a known argument with optional default value"""
        self.default_group.add_argument(name, default, help, required)

    def dump_default_config(self, dest=None):
        """Generate a default config file based on known arguments"""
        config = "\n".join([group.dump_default_config() for group in self.known_groups])
        if dest:
            dest.write(config)
        return config

    def load_config(self) -> Dict[str, Any]:
        """Find and load TOML config file from various locations:
        - $HOME/.config/llmse6/config.toml
        - Current directory/.llmse6.config.toml
        - Specified file
        Later file have higher priorities.
        """
        search_paths = []
        home_config = Path.home() / ".config" / "llmse6" / "config.toml"
        search_paths.append(home_config)
        current_dir = Path.cwd()
        search_paths.append(current_dir / ".llmse6.config.toml")
        if self.config_files:
            search_paths.extend(self.config_files)

        config = {}
        for path in search_paths:
            if path.exists():
                with open(path, "rb") as f:
                    config = deep_merge(config, tomli.load(f))

        self._raw_data = config
        return config


class ArgumentGroup:
    """Helper class for grouping arguments in TOML tables"""

    def __init__(self, parent, name, help="", expose_raw=False):
        self.parent = parent
        self.name = name
        self.known_args = {}
        self.help = help
        self.parsed = Config({})
        self._raw_data = None
        self.expose_raw = expose_raw

    def parse_args(self):
        self._parse_group()
        for name, info in self.known_args.items():
            self._parse_argument(name, info["default"])
        return self.parsed

    def _parse_group(self):
        groups = self.name.split(".")
        raw = self.parent._raw_data

        for g in groups:
            if raw and g in raw:
                raw = raw[g]
            else:
                raw = {}
                break
        self._raw_data = raw

        parsed = self.parent.parsed
        for g in groups:
            parsed = parsed.setdefault(g, Config({}))
        if self.expose_raw:
            parsed.update(self._raw_data)
        self.parsed = parsed

    def _parse_argument(self, name, default):
        value = default
        if self._raw_data and name in self._raw_data:
            value = self._raw_data[name]
        self.parsed[name] = value

    def add_argument(
        self, name: str, default=None, help: str = "", required: bool = False
    ):
        """Add an argument to this group

        Args:
            name: Argument name (will be nested under the group in TOML)
            default: Default value if not specified
            help: Description of the argument
            required: Whether this argument is required

        Returns:
            The current value of this argument, or the default
        """

        self.known_args[name] = {
            "default": default,
            "help": help,
            "required": required,
        }

    def dump_default_config(self):
        """Generate a default config file based on known arguments"""

        config_text = f"[{self.name}]\n"
        # First add all ungrouped arguments
        for name, info in self.known_args.items():
            config_text += f"# {info['help']}\n"
            if info["required"]:
                config_text += "# Required: Yes\n"

            default = info["default"]
            if default is None:
                config_text += f"# {name} = \n\n"
            else:
                config_text += f"# {name} = {default}\n\n"

        return config_text


class Config(dict):
    """Wrapper class that allows both dot notation and dictionary-style access to fields"""

    def __getattr__(self, name):
        if name in self:
            value = self[name]
            if isinstance(value, dict):
                return Config(value)
            return value
        raise AttributeError(f"'Config' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        self[name] = value
