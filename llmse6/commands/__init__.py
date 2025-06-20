import json
import logging
import re

import yaml
from prompt_toolkit.completion import Completer, Completion

logger = logging.getLogger(__name__)


def parse_cmdline(cmdline):
    if not cmdline.startswith("/"):
        return None, None

    cmd = cmdline.split(" ", 1)
    c_name = cmd[0][1:]
    c_arg = cmd[1] if len(cmd) > 1 else None
    return c_name, c_arg


class CommandCompleter(Completer):
    """Main completer that delegates to specific command completers"""

    def __init__(self, manager):
        self.command_manager = manager

    def get_completions(self, document, complete_event):
        text = document.text

        name, args = parse_cmdline(text)
        if not name:
            return
        if args is None:  # Complete command names
            candidates = self.command_manager.command_names()
            for candidate in candidates:
                if name in candidate:
                    yield Completion(
                        candidate, start_position=-len(name), display=candidate
                    )
            return

        yield from self.command_manager.get_completions(name, args, document)


class Command:
    """Base class for agent commands"""

    command: str = ""
    description: str = ""

    def __init__(self, agent):
        self.agent = agent

    def slashes(self) -> list[str]:
        return [self.command]

    def execute(self, name: str, arg: str):
        """Execute command with given input"""
        raise NotImplementedError


class FileCommand(Command):
    description = (
        "Add/Drop files to context - /add <file1> [file2...];  /drop <file1> [file2...]"
    )

    def slashes(self) -> list[str]:
        return ["add", "drop"]

    def execute(self, name: str, arg: str):
        chat_files = self.agent.state.chat_files
        files = arg.split(" ")
        if not files:
            print("Please specify files.")
            return
        if name == "add":
            result = chat_files.add_by_names(files)
            for f in result.get("not_exist"):
                print(f"{f} doesn't exist, ignoring.")
        else:
            for f in files:
                p = chat_files.normalize(f)
                chat_files.remove(p)

    def get_completions(self, name, args, document):
        # Parse the arguments to get the current word being completed
        if not args:
            current_word = ""
        else:
            parts = args.split()
            if args.endswith(" "):
                current_word = ""
            else:
                current_word = parts[-1] if parts else ""

        if name == "add":
            candidates = self.agent.state.chat_files.candidates()
        elif name == "drop":
            candidates = [str(f) for f in self.agent.state.chat_files.list()]
        else:
            candidates = []

        # Filter candidates based on current word
        for candidate in candidates:
            if current_word in candidate:
                yield Completion(
                    candidate, start_position=-len(current_word), display=candidate
                )


class ModelCommand(Command):
    command = "model"
    description = "Switch LLM model - /model <model_name>"

    def execute(self, name: str, new_model: str):
        if not new_model:
            print("Please specify a model name")
            return
        self.agent.provider_model = new_model
        print(f"Switched to model: {new_model}")


class SaveCommand(Command):
    command = "save"
    description = "Save last response - /save [filename] (default: output.md)"

    def __init__(self, agent, tag_name: str | None = None, default_file: str = ""):
        super().__init__(agent)
        self.tag_name = tag_name or f"{agent.name}_content"
        self.default_file = default_file or f"{agent.name}_output.md"

    def execute(self, name: str, arg: str):
        output_file = arg if arg else self.default_file
        last_message = self.agent.state.last_message()
        self._save_content(last_message, self.tag_name, output_file)
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

    async def execute(self, name: str, arg: str):
        tool_registry = self.agent.tool_registry

        parts = arg.split(maxsplit=1)
        if len(parts) < 1:
            print("Usage: /invoke-tool <function_name> [json_args]")
            return

        function_name = parts[0]
        args_str = parts[0] if len(parts) > 1 else "{}"

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

    async def execute(self, name: str, arg: str):
        tool_registry = self.agent.tool_registry
        tool_specs = tool_registry.get_tools_specs()
        if not tool_specs:
            print("No tools registered.")
            return

        print("Registered Tools:")
        print(yaml.safe_dump(tool_specs))


class InfoCommand(Command):
    command = "info"
    description = "Show current chat files and model in use - /info"

    def execute(self, name: str, arg: str):
        # Show current model
        current_model = getattr(self.agent, "provider_model", "Unknown")
        print(f"Current model: {current_model}")

        # Show chat files
        chat_files = self.agent.state.chat_files.list()
        if chat_files:
            print(f"\nChat files ({len(chat_files)}):")
            for file_path in chat_files:
                print(f"  - {file_path}")
        else:
            print("\nNo chat files currently loaded.")


class ResetCommand(Command):
    command = "reset"
    description = "Reset chat history and chat files - /reset"

    def execute(self, name: str, arg: str):
        self.agent.state.reset()
        print("Reset complete.")


class CommitCommand(Command):
    command = "commit"
    description = "Auto-commit changes using GitCommitAgent - /commit"

    async def execute(self, name: str, arg: str):
        commit_agent = self.agent.context.get("commit_agent")
        if not commit_agent:
            print("No commit agent, ignoring.")
        result = await commit_agent.auto_commit_changes()
        print(result)
