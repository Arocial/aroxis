import asyncio
import logging
from enum import Enum

from kissllm.io import IOChannel, IOTypeEnum
from kissllm.utils import format_prompt
from textual import events
from textual.app import App, ComposeResult
from textual.widgets import Collapsible, Footer, Label, TextArea

from arox.utils import user_input_generator as user_input_generator

logger = logging.getLogger(__name__)


def _hack_textual_keys():
    from textual._ansi_sequences import ANSI_SEQUENCES_KEYS

    class HKeys(str, Enum):
        @property
        def value(self) -> str:
            return super().value

        AltEnter = "alt+enter"

    ANSI_SEQUENCES_KEYS["\x1b\r"] = (HKeys.AltEnter,)


_hack_textual_keys()


class TUIByIO(App, IOChannel):
    BINDINGS = [
        ("c", "collapse_or_expand(True)", "Collapse All"),
        ("e", "collapse_or_expand(False)", "Expand All"),
    ]

    CSS = """
    TextArea {
        width: 100%;
        height: auto;
    }
    .wrapped {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Footer()

    def action_collapse_or_expand(self, collapse: bool) -> None:
        for child in self.walk_children(Collapsible):
            child.collapsed = collapse

    def create_sub_channel(self, channel_type, title=""):
        io_channel = TextualIOChannel(self, channel_type, title)
        return io_channel

    @property
    def app(self):
        return self


class UserInput(TextArea):
    BINDINGS = [
        ("ctrl+j", "submit", "Submit"),
        ("alt+enter", "submit", "Submit"),
    ]

    def __init__(self, input_future, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_future = input_future

    async def _on_key(self, event: events.Key) -> None:
        # Textual parses shift+enter this way.
        # One can use [tkrec](https://github.com/Textualize/textual-key-recorder/)
        # to see the keys result in textual app.
        if event.key == "enter" and event.character is None:
            event.prevent_default()
            self.action_submit()
        else:
            return await super()._on_key(event)

    def action_submit(self) -> None:
        """Submit the input."""
        user_input = self.text
        if self.input_future and not self.input_future.done():
            self.input_future.set_result(user_input)


class CollapsibleLabel(Collapsible):
    def __init__(self, content="", title="", collapsed=True):
        self.label_widget = Label(content, markup=False, classes="wrapped")
        super().__init__(self.label_widget, title=title, collapsed=collapsed)

    def update(self, content):
        self.label_widget.update(content)


class TextualIOChannel(IOChannel):
    def __init__(self, parent, channel_type, title=""):
        self.parent = parent
        self.app = self.parent.app
        self.output_widget = None
        self.channel_type = channel_type
        title = title or (
            str(channel_type.value)
            if isinstance(channel_type, Enum)
            else str(channel_type)
        )
        self.title = f"{self.parent.title}.{title}"
        self._accu = ""

    async def read(self):
        while True:
            input_future = asyncio.get_running_loop().create_future()
            input_widget = UserInput(input_future)
            await self.app.mount(input_widget)
            input_widget.focus()
            user_input = await input_future
            await input_widget.remove()
            collapsible = Collapsible(
                Label(user_input, markup=False, classes="wrapped"),
                collapsed=False,
                title=f"{self.title}.User",
            )
            await self.app.mount(collapsible)
            yield user_input

    async def write(self, content, metadata=None):
        output_widget = Label(str(content))
        await self.app.mount(output_widget)

    def create_sub_channel(self, channel_type, title=""):
        if channel_type == IOTypeEnum.prompt_message:
            return PromptMessageWidget(self, channel_type, title)
        elif channel_type == IOTypeEnum.streaming_assistant:
            return StreamingOutputWidget(self, channel_type, title)

        return self.__class__(self, channel_type, title)


class PromptMessageWidget(IOChannel):
    def __init__(self, parent, channel_type, title=""):
        self.parent = parent
        self.app = self.parent.app
        title = title or (
            str(channel_type.value)
            if isinstance(channel_type, Enum)
            else str(channel_type)
        )
        self.title = f"{self.parent.title}.{title}"

    async def write(self, content, metadata=None):
        output_widget = CollapsibleLabel(
            "\n".join(format_prompt(content)),
            title=self.title,
            collapsed=True,
        )
        await self.app.mount(output_widget)


class StreamingOutputWidget(IOChannel):
    def __init__(self, parent, channel_type, title=""):
        self.parent = parent
        self.app = self.parent.app
        self.output_widget = None
        title = title or (
            str(channel_type.value)
            if isinstance(channel_type, Enum)
            else str(channel_type)
        )
        self.title = f"{self.parent.title}.{title}"
        self.accumulated_content = ""

    async def write(self, content, metadata=None):
        if self.output_widget is None:
            self.output_widget = CollapsibleLabel(title=self.title, collapsed=True)
            await self.app.mount(self.output_widget)

        if content:
            self.accumulated_content += str(content)

        self.output_widget.update(self.accumulated_content)
