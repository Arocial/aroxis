import asyncio
import logging
from enum import Enum

from kissllm.io import IOChannel, IOTypeEnum, OutputItem
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
    def __init__(self, *args, **kwargs):
        self.label_widget = Label(markup=False, classes="wrapped")
        super().__init__(self.label_widget, *args, **kwargs)

    def update(self, content):
        self.label_widget.update(content)


class TextualIOChannel:
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

    async def write(self, output_item: OutputItem):
        if self.output_widget is None:
            self.output_widget = CollapsibleLabel(title=self.title, collapsed=True)
            await self.app.mount(self.output_widget)

        if output_item.content:
            if self.channel_type == IOTypeEnum.prompt_message:
                self._accu = "\n".join(format_prompt(output_item.content))
            else:
                self._accu += str(output_item.content)

        self.output_widget.update(self._accu)

    def create_sub_channel(self, channel_type, title=""):
        io_channel = self.__class__(self, channel_type, title)
        return io_channel
