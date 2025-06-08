import json
import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class Command:
    """Base class for agent commands"""

    command: str = ""
    description: str = ""

    def __init__(self, agent):
        self.agent = agent

    def slashs(self) -> list[str]:
        return [self.command]

    def execute(self, user_input: str):
        """Execute command with given input"""
        raise NotImplementedError


class FileCommand(Command):
    description = (
        "Add/Drop files to context - /add <file1> [file2...];  /drop <file1> [file2...]"
    )

    def slashs(self) -> list[str]:
        return ["add", "drop"]

    def normalize(self, path: str):
        workspace = self.agent.workspace
        # normalize file path to relative to workspace if it's subtree of workspace, otherwise absolute.
        p = Path(path)
        if not p.is_absolute():
            p = (workspace / p).absolute()
        if p.is_relative_to(workspace):
            p = p.relative_to(workspace)
        return p

    def execute(self, user_input: str):
        all_files = self.agent.additional_files
        splited = user_input.split()
        command = splited[0][1:]
        files = splited[1:]
        if not files:
            print("Please specify files.")
            return
        if command == "add":
            for f in files:
                p = self.normalize(f)
                if p.exists():
                    all_files.append(p)
                else:
                    logger.warning(f"{p} doesn't exist, ignoring.")
        else:
            for f in files:
                p = self.normalize(f)
                if p in all_files:
                    all_files.remove(p)


class ModelCommand(Command):
    command = "model"
    description = "Switch LLM model - /model <model_name>"

    def execute(self, user_input: str):
        parts = user_input.split()
        if len(parts) < 2:
            print("Please specify a model name")
            return
        new_model = parts[1]
        self.agent.provider_model = new_model
        print(f"Switched to model: {new_model}")


class SaveCommand(Command):
    command = "save"
    description = "Save last response - /save [filename] (default: output.md)"

    def __init__(self, agent, tag_name: str | None = None, default_file: str = ""):
        super().__init__(agent)
        self.tag_name = tag_name or f"{agent.name}_content"
        self.default_file = default_file or f"{agent.name}_output.md"

    def execute(self, user_input: str):
        parts = user_input.split()
        output_file = parts[1] if len(parts) > 1 else self.default_file
        last_message = self.agent.state["messages"][-1]
        self._save_content(last_message.content, self.tag_name, output_file)
        print(f"Saved to {output_file}!")

    def _save_content(self, content_msg: str, tag_name: str | None, file_name: str):
        """Save content from message to file"""
        if tag_name is not None:
            pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
            match = re.search(pattern, content_msg, re.DOTALL)

            if match:
                result = match.group(1)
            else:
                result = content_msg
        else:
            result = content_msg
        output_path = self.agent.workspace / file_name
        print(f"Saving content to {output_path}")
        with output_path.open("w") as f:
            f.write(result)


class InvokeToolCommand(Command):
    command = "invoke-tool"
    description = "Invoke a registered tool - /invoke-tool <function_name> [json_args]"

    async def execute(self, user_input: str):
        tool_registry = self.agent.tool_registry

        parts = user_input.split(maxsplit=2)
        if len(parts) < 2:
            print("Usage: /invoke-tool <function_name> [json_args]")
            return

        function_name = parts[1]
        args_str = parts[2] if len(parts) > 2 else "{}"

        try:
            args = json.loads(args_str)
            if not isinstance(args, dict):
                raise ValueError("Arguments must be a JSON object (dictionary).")
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON arguments: {e}")
            return
        except ValueError as e:
            print(f"Error: {e}")
            return

        # Prepare the tool_call structure expected by execute_tool_call
        # Note: We don't have a real tool_call ID here, as it's a direct invocation.
        tool_call_data = {
            "id": f"cmd_{function_name}",  # Generate a placeholder ID
            "type": "function",
            "function": {"name": function_name, "arguments": json.dumps(args)},
        }

        try:
            print(f"Invoking tool '{function_name}' with args: {args}")
            result = await tool_registry.execute_tool_call(tool_call_data)
            print(f"Tool '{function_name}' executed successfully.")
            print("Result:")
            print(result)
        except ValueError as e:
            print(f"Error invoking tool '{function_name}': {e}")
        except ConnectionError as e:
            print(f"Error connecting to MCP server for tool '{function_name}': {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error invoking tool '{function_name}': {e}", exc_info=True
            )
            print(f"An unexpected error occurred: {e}")


class ListToolCommand(Command):
    command = "list-tools"
    description = "List all registered tools"

    async def execute(self, user_input: str):
        tool_registry = self.agent.tool_registry
        tool_specs = tool_registry.get_tools_specs()
        if not tool_specs:
            print("No tools registered.")
            return

        print("Registered Tools:")
        print(yaml.safe_dump(tool_specs))
