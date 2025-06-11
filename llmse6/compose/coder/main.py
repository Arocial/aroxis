import argparse
import asyncio
import logging
import sys
from pathlib import Path

from kissllm.tools import LocalToolManager

from llmse6 import agents
from llmse6.agents.chat import ChatAgent
from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.commands import CommandCompleter
from llmse6.compose.coder.state import CoderState
from llmse6.config import TomlConfigParser
from llmse6.tools import file_edit
from llmse6.utils import user_input_generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.debug("Starting main function")
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dump-default-config",
        help="Dump default config to specified file and exit.",
        default="",
    )
    args = parser.parse_args()

    default_agent_config = Path(__file__).parent / "config.toml"
    toml_parser = TomlConfigParser(config_files=[default_agent_config])
    agents.init(toml_parser)
    local_tool_manager = LocalToolManager()

    diff_agent = LLMBaseAgent("smart-diff", toml_parser)
    file_edit_tool = file_edit.FileEdit(diff_agent)
    file_edit_tool.register_tools(local_tool_manager)

    coder_agent = ChatAgent("coder", toml_parser, local_tool_manager, CoderState)

    if args.dump_default_config:
        logger.debug(f"Dumping default config to {args.dump_default_config}")
        with open(args.dump_default_config, "w") as f:
            toml_parser.dump_default_config(f)
        sys.exit(0)

    test_user_msg = []
    logger.debug("Starting coder agent")
    await coder_agent.start(
        user_input_generator(
            completer=CommandCompleter(coder_agent.command_manager),
            cached_human_responses=test_user_msg,
            force_cached=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
