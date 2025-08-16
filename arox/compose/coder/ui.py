import asyncio

from kissllm.io import SimpleTextUI

from arox.commands import CommandCompleter
from arox.compose.coder.main import CoderComposer
from arox.ui import TUIByIO
from arox.utils import user_input_generator


class CoderTUI(TUIByIO):
    def on_mount(self) -> None:
        composer = CoderComposer(self.io_channel)
        self.input_suggester = CommandCompleter(
            composer.coder_agent.command_manager
        ).textual_suggester
        self.run_worker(composer.run, name="composer", exclusive=True)


class CoderTextUI(SimpleTextUI):
    def run(self):
        composer = CoderComposer(self.io_channel)
        self.input_generator = user_input_generator(
            completer=CommandCompleter(composer.coder_agent.command_manager)
        )
        asyncio.run(composer.run())
