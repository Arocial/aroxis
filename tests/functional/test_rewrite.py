from pathlib import Path

import pytest
from kissllm.io import SimpleTextUI
from prompt_toolkit.input import create_pipe_input

from arox import agent_patterns, commands
from arox.agent_patterns.chat import ChatAgent
from arox.config import TomlConfigParser
from arox.utils import user_input_generator


@pytest.mark.asyncio
async def test_rewrite_agent():
    current_dir = Path(__file__).parent.absolute()
    default_agent_config = current_dir / "rewrite.toml"
    toml_parser = TomlConfigParser(
        config_files=[default_agent_config],
        override_configs={"workspace": str(current_dir)},
    )
    agent_patterns.init(toml_parser)
    file_name = Path(__file__).parent / "test_sample.md"
    test_user_msg = [
        f"/add {file_name}\n",
        "Translate the content to Chinese.\n",
        f"/save {file_name}.testres\n",
        "\x04",
    ]
    with create_pipe_input() as pipe_input:
        text_ui = SimpleTextUI("rewrite", user_input_generator(input=pipe_input))
        io_channel = text_ui.io_channel
        agent = ChatAgent("rewrite", toml_parser, io_channel=io_channel)

        cmds = [commands.FileCommand(agent), commands.SaveCommand(agent)]
        agent.register_commands(cmds)
        io_channel.input_generator = user_input_generator(input=pipe_input)

        for msg in test_user_msg:
            pipe_input.send_text(msg)
        await agent.start()
