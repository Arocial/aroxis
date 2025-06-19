import argparse
import asyncio
import logging
import sys
from pathlib import Path

from kissllm.tools import LocalToolManager

from llmse6 import agent_patterns, commands, config
from llmse6.agent_patterns.chat import ChatAgent
from llmse6.agent_patterns.llm_base import LLMBaseAgent
from llmse6.commands import CommandCompleter
from llmse6.compose.coder.state import CoderState
from llmse6.compose.git_commit import GitCommitAgent
from llmse6.config import TomlConfigParser
from llmse6.tools import file_edit, search_reading
from llmse6.utils import user_input_generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoderComposer:
    def __init__(self):
        parser = argparse.ArgumentParser()

        parser.add_argument(
            "--dump-default-config",
            help="Dump default config to specified file and exit.",
            default="",
        )
        args, unknown_args = parser.parse_known_args()
        cli_configs = config.parse_dot_config(unknown_args)

        default_agent_config = Path(__file__).parent / "config.toml"
        toml_parser = TomlConfigParser(config_files=[default_agent_config],
                                       override_configs=cli_configs)
        agent_patterns.init(toml_parser)
        local_tool_manager = LocalToolManager()

        diff_agent = LLMBaseAgent("smart-diff", toml_parser)
        file_edit_tool = file_edit.FileEdit(diff_agent)
        file_edit_tool.register_tools(local_tool_manager)
        self.diff_agent = diff_agent

        git_commit_agent = GitCommitAgent("git_commit_agent", toml_parser)
        self.commit_agent = git_commit_agent

        coder_agent = ChatAgent(
            "coder",
            toml_parser,
            local_tool_manager,
            CoderState,
            context={"commit_agent": self.commit_agent},
        )
        sr_tool = search_reading.SearchReading(coder_agent.state)
        sr_tool.register_tools(local_tool_manager)

        coder_commands = [
            commands.FileCommand(coder_agent),
            commands.ModelCommand(coder_agent),
            commands.InvokeToolCommand(coder_agent),
            commands.ListToolCommand(coder_agent),
            commands.ResetCommand(coder_agent),
            commands.InfoCommand(coder_agent),
            commands.CommitCommand(coder_agent),
        ]
        coder_agent.register_commands(coder_commands)

        self.coder_agent = coder_agent

        if args.dump_default_config:
            logger.debug(f"Dumping default config to {args.dump_default_config}")
            with open(args.dump_default_config, "w") as f:
                toml_parser.dump_default_config(f)
            sys.exit(0)

    async def run(self):
        test_user_msg = []
        logger.debug("Starting coder agent")
        await self.coder_agent.start(
            user_input_generator(
                completer=CommandCompleter(self.coder_agent.command_manager),
                cached_human_responses=test_user_msg,
                force_cached=False,
            )
        )


def main():
    asyncio.run(CoderComposer().run())


if __name__ == "__main__":
    main
