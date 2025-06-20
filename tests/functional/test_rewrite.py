from pathlib import Path

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from llmse6 import agent_patterns, commands
from llmse6.agent_patterns.chat import ChatAgent
from llmse6.config import TomlConfigParser
from llmse6.utils import user_input_generator


@pytest.mark.asyncio
async def test_rewrite_agent():
    current_dir = Path(__file__).parent.absolute()
    default_agent_config = current_dir / "rewrite.toml"
    toml_parser = TomlConfigParser(
        config_files=[default_agent_config],
        override_configs={"workspace": str(current_dir)},
    )
    agent_patterns.init(toml_parser)
    agent = ChatAgent("rewrite", toml_parser)

    cmds = [commands.FileCommand(agent), commands.SaveCommand(agent)]
    agent.register_commands(cmds)

    file_name = Path(__file__).parent / "test_sample.md"
    test_user_msg = [
        f"/add {file_name}",
        "Translate the content to Chinese.",
        f"/save {file_name}.testres",
        "q",
    ]
    with create_pipe_input() as pipe_input:
        for msg in test_user_msg:
            pipe_input.send_text(msg + "\n")
        await agent.start(user_input_generator(input=pipe_input, output=DummyOutput()))
