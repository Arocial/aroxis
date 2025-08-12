import asyncio

from kissllm.io import IOChannel

from arox.commands import CommandCompleter
from arox.compose.coder.main import CoderComposer
from arox.ui import TUIByIO
from arox.utils import user_input_generator


class CoderTUI(TUIByIO):
    def on_mount(self) -> None:
        composer = CoderComposer(self)
        self.input_suggester = CommandCompleter(
            composer.coder_agent.command_manager
        ).textual_suggester
        self.run_worker(composer.run, name="composer", exclusive=True)


class CoderTextUI(IOChannel):
    def __init__(self, channel_type, app=None):
        self.app = app if app else self
        self.composer = None
        super().__init__(channel_type)

    def create_sub_channel(self, channel_type, title=""):
        return self.__class__(channel_type, self)

    async def read(self):
        async for user_input in user_input_generator(
            completer=CommandCompleter(self.app.composer.coder_agent.command_manager)
        ):
            yield user_input

    def run(self):
        self.composer = CoderComposer(self)
        asyncio.run(self.composer.run())
