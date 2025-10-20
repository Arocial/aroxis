import json
import logging
import re

import yaml
from prompt_toolkit.completion import Completer, Completion
from textual.widgets import TextArea

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
        yield from self._get_completions(document.text)

    def _get_completions(self, text):
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

        yield from self.command_manager.get_completions(name, args)

    def textual_suggester(self, text_area: TextArea):
        current_location = text_area.cursor_location
        text = text_area.document.get_text_range((0, 0), current_location)
        yield from self._get_completions(text)


class Command:
    """Base class for agent commands"""

    command: str = ""
    description: str = ""

    def __init__(self, agent):
        self.agent = agent

    def slashes(self) -> list[str]:
        return [self.command]

    async def execute(self, name: str, arg: str):
        """Execute command with given input"""
        raise NotImplementedError

    def get_completions(self, name, args):
        yield from []


class FileCommand(Command):
    description = (
        "Add/Drop files to context - /add <file1> [file2...];  /drop <file1> [file2...]"
    )

    def slashes(self) -> list[str]:
        return ["add", "drop"]

    async def execute(self, name: str, arg: str):
        chat_files = self.agent.state.chat_files
        files = arg.split(" ")
        if not files:
            await self.agent.io_channel.write("Please specify files.")
            return
        if name == "add":
            result = chat_files.add_by_names(files)
            for f in result.get("not_exist"):
                await self.agent.io_channel.write(f"{f} doesn't exist, ignoring.")
        else:
            for f in files:
                p = chat_files.normalize(f)
                await chat_files.remove(p)

    def get_completions(self, name, args):
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

    async def execute(self, name: str, new_model: str):
        if not new_model:
            await self.agent.io_channel.write("Please specify a model name")
            return
        self.agent.set_model(new_model)


class SaveCommand(Command):
    command = "save"
    description = "Save last response - /save [filename] (default: output.md)"

    def __init__(self, agent, tag_name: str | None = None, default_file: str = ""):
        super().__init__(agent)
        self.tag_name = tag_name or f"{agent.name}_content"
        self.default_file = default_file or f"{agent.name}_output.md"

    async def execute(self, name: str, arg: str):
        output_file = arg if arg else self.default_file
        last_message = self.agent.last_message()
        await self._save_content(last_message, self.tag_name, output_file)
        await self.agent.io_channel.write(f"Saved to {output_file}!")

    async def _save_content(
        self, content_msg: str, tag_name: str | None, file_name: str
    ):
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
        await self.agent.io_channel.write(f"Saving content to {output_path}")
        with output_path.open("w") as f:
            f.write(result)


class InvokeToolCommand(Command):
    command = "invoke-tool"
    description = "Invoke a registered tool - /invoke-tool <function_name> [json_args]"

    async def execute(self, name: str, arg: str):
        tool_registry = self.agent.tool_registry

        parts = arg.split(maxsplit=1)
        if len(parts) < 1:
            await self.agent.io_channel.write(
                "Usage: /invoke-tool <function_name> [json_args]"
            )
            return

        function_name = parts[0]
        args_str = parts[0] if len(parts) > 1 else "{}"

        try:
            args = json.loads(args_str)
            if not isinstance(args, dict):
                raise ValueError("Arguments must be a JSON object (dictionary).")
        except json.JSONDecodeError as e:
            await self.agent.io_channel.write(f"Error: Invalid JSON arguments: {e}")
            return
        except ValueError as e:
            await self.agent.io_channel.write(f"Error: {e}")
            return

        # Prepare the tool_call structure expected by execute_tool_call
        # Note: We don't have a real tool_call ID here, as it's a direct invocation.
        tool_call_data = {
            "id": f"cmd_{function_name}",  # Generate a placeholder ID
            "type": "function",
            "function": {"name": function_name, "arguments": json.dumps(args)},
        }

        try:
            await self.agent.io_channel.write(
                f"Invoking tool '{function_name}' with args: {args}"
            )
            result = await tool_registry.execute_tool_call(tool_call_data)
            await self.agent.io_channel.write(
                f"Tool '{function_name}' executed successfully."
            )
            await self.agent.io_channel.write("Result:")
            await self.agent.io_channel.write(result)
        except ValueError as e:
            await self.agent.io_channel.write(
                f"Error invoking tool '{function_name}': {e}"
            )
        except ConnectionError as e:
            await self.agent.io_channel.write(
                f"Error connecting to MCP server for tool '{function_name}': {e}"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error invoking tool '{function_name}': {e}", exc_info=True
            )
            await self.agent.io_channel.write(f"An unexpected error occurred: {e}")


class ListToolCommand(Command):
    command = "list-tools"
    description = "List all registered tools"

    async def execute(self, name: str, arg: str):
        tool_registry = self.agent.tool_registry
        tool_specs = tool_registry.get_tools_specs()
        if not tool_specs:
            await self.agent.io_channel.write("No tools registered.")
            return

        await self.agent.io_channel.write("Registered Tools:")
        await self.agent.io_channel.write(yaml.safe_dump(tool_specs))


class InfoCommand(Command):
    command = "info"
    description = "Show current chat files and model in use - /info"

    async def execute(self, name: str, arg: str):
        # Show current model
        current_model = getattr(self.agent, "provider_model", "Unknown")
        await self.agent.io_channel.write(f"Current model: {current_model}")

        # Show chat files
        chat_files = self.agent.state.chat_files.list()
        if chat_files:
            await self.agent.io_channel.write(f"\nChat files ({len(chat_files)}):")
            for file_path in chat_files:
                await self.agent.io_channel.write(f"  - {file_path}")
        else:
            await self.agent.io_channel.write("\nNo chat files currently loaded.")


class ResetCommand(Command):
    command = "reset"
    description = "Reset chat history and chat files - /reset"

    async def execute(self, name: str, arg: str):
        self.agent.state.reset()
        await self.agent.io_channel.write("Reset complete.")


class CommitCommand(Command):
    command = "commit"
    description = "Auto-commit changes using GitCommitAgent - /commit"

    async def execute(self, name: str, arg: str):
        commit_agent = self.agent.context.get("commit_agent")
        if not commit_agent:
            await self.agent.io_channel.write("No commit agent, ignoring.")
        result = await commit_agent.auto_commit_changes()
        await self.agent.io_channel.write(result)
