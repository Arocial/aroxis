import asyncio
import logging
from enum import Enum
from typing import Callable, Iterable, Optional

from kissllm.io import IOChannel, IOTypeEnum
from kissllm.utils import format_prompt
from prompt_toolkit.completion import Completion
from prompt_toolkit.history import FileHistory, History
from textual import events
from textual.app import App, ComposeResult
from textual.widgets import Collapsible, Footer, Label, ListItem, ListView, TextArea

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
    SuggestionPopup {
        background: $panel;
        border: round $accent;
        padding: 1 1;
        width: auto;
        layer: popup;
        max-height: 10;
    }
    """

    def __init__(self):
        self.input_suggester = None
        super().__init__()

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


class SuggestionPopup(ListView):
    """A popup widget for displaying suggestions."""

    def __init__(self, suggestions: list[Completion], *args, **kwargs):
        self.suggestions = suggestions
        items = [ListItem(Label(suggestion.display_text)) for suggestion in suggestions]
        super().__init__(*items, *args, **kwargs)

    def get_selected_suggestion(self) -> Completion:
        if 0 <= self.index < len(self.suggestions):
            return self.suggestions[self.index]
        return Completion("")

    def move_selection(self, direction: int):
        """Move selection up (-1) or down (1)."""
        new_index = self.index + direction
        if 0 <= new_index < len(self.suggestions):
            self.index = new_index


class UserInput(TextArea):
    BINDINGS = [
        ("ctrl+j", "submit", "Submit"),
        ("alt+enter", "submit", "Submit"),
        ("up", "on_up", "Previous"),
        ("down", "on_down", "Next"),
        ("ctrl+r", "history_search", "Search History"),
        ("ctrl+g", "on_abort", "Abort"),
        ("escape", "on_abort", "Abort"),
        ("tab", "accept_suggestion", "Accept Suggestion"),
    ]

    def __init__(
        self,
        input_future,
        history: History = None,
        suggester: Optional[Callable[[TextArea], Iterable[Completion]]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.input_future = input_future
        self.submit_history = history
        self.history_index = -1  # -1 means no history active
        self.history_search_text = ""
        self.history_search_mode = False
        self.suggester = suggester
        self.suggestion_popup: Optional[SuggestionPopup] = None
        self.suggestions_visible = False

    async def _on_key(self, event: events.Key) -> None:
        continue_super = True

        if self.history_search_mode:
            continue_super = False
            if not event.is_printable:
                await self.history_search_exit()
            else:
                event.prevent_default()
                self.history_search_text += event.character
                await self.action_history_search()

        # Textual parses shift+enter this way.
        # One can use [tkrec](https://github.com/Textualize/textual-key-recorder/)
        # to see the keys result in textual app.
        if event.key == "enter" and event.character is None:
            event.prevent_default()
            await self.action_submit()
            continue_super = False

        if continue_super:
            result = await super()._on_key(event)
            # Update suggestions after text change if suggester is available
            if event.is_printable and self.suggester:
                await self.update_suggestions()
            return result

    async def action_submit(self) -> None:
        """Submit the input."""
        user_input = self.text
        if self.submit_history and user_input:
            self.submit_history.append_string(user_input)
        if self.input_future and not self.input_future.done():
            self.input_future.set_result(user_input)

    @property
    async def loaded_history(self):
        return [h async for h in self.submit_history.load()]

    async def action_history_search(self):
        """Search history matching current input."""
        if not self.submit_history:
            return

        if not self.history_search_mode:
            self.history_search_mode = True
            self.history_search_text = self.text
        history = await self.loaded_history
        for i in range(self.history_index, len(history)):
            if self.history_search_text.lower() in history[i].lower():
                self.history_index = i
                self.text = (
                    f"(search-history) `{self.history_search_text}`: {history[i]}"
                )
                break
        else:
            self.text = f"(search-history) `{self.history_search_text}`: {history[self.history_index]}"

    async def history_search_exit(self, find=True):
        if self.history_search_mode:
            self.text = (
                (await self.loaded_history)[self.history_index]
                if find
                else self.history_search_text
            )
            self.history_index = -1
            self.history_search_mode = False

    async def action_on_abort(self):
        """Reset history navigation state."""
        if self.suggestions_visible and self.suggestion_popup:
            await self.action_hide_suggestions()
            return

        if self.history_search_mode:
            await self.history_search_exit(find=False)
            self.text = self.history_search_text

    async def action_on_up(self):
        """Navigate to previous suggestion item or history item."""
        if self.suggestions_visible and self.suggestion_popup:
            self.suggestion_popup.move_selection(-1)
            return

        if not self.submit_history:
            return
        await self.history_search_exit()
        history = await self.loaded_history
        if self.history_index < len(history) - 1:
            self.history_index += 1
            self.text = history[self.history_index]

    async def action_on_down(self):
        """Navigate to next suggestion item or history item."""
        if self.suggestions_visible and self.suggestion_popup:
            self.suggestion_popup.move_selection(1)
            return

        if not self.submit_history:
            return
        await self.history_search_exit()
        history = await self.loaded_history
        if self.history_index > 0:
            self.history_index -= 1
            self.text = history[self.history_index]
        elif self.history_index == 0:
            self.history_index = -1
            self.text = self.history_search_text

    async def update_suggestions(self):
        """Update suggestions based on current text."""
        if not self.suggester:
            return

        suggestions = list(self.suggester(self))

        if suggestions:
            await self.show_suggestions(suggestions)
        else:
            await self.action_hide_suggestions()

    async def show_suggestions(self, suggestions: list[Completion]):
        """Show the suggestion popup with given suggestions."""
        await self.action_hide_suggestions()  # Hide any existing popup

        if not suggestions:
            return

        self.suggestion_popup = SuggestionPopup(suggestions)

        # Position popup intelligently
        cursor_offset = self.cursor_screen_offset
        # Get the size of the terminal
        terminal_size = self.app.size
        popup_width = (
            max(len(s.display_text) for s in suggestions) + 6
        )  # Add some padding
        popup_height = min(len(suggestions), 10) + 2  # Limit height to 10 items

        # Calculate x position (prevent right overflow)
        matched_len = suggestions[0].start_position if suggestions else 0
        x_pos = min(cursor_offset[0] + matched_len, terminal_size.width - popup_width)

        # Calculate y position (flip to above if below is not enough space)
        if cursor_offset[1] + popup_height + 1 <= terminal_size.height:
            # Place below cursor
            y_pos = cursor_offset[1] + 1
        else:
            # Place above cursor
            y_pos = cursor_offset[1] - popup_height

        popup_offset = (x_pos, y_pos)
        self.suggestion_popup.styles.offset = popup_offset
        self.suggestion_popup.styles.width = popup_width

        await self.app.mount(self.suggestion_popup)
        self.suggestions_visible = True

    async def action_hide_suggestions(self):
        """Hide the suggestion popup."""
        if self.suggestion_popup:
            await self.suggestion_popup.remove()
            self.suggestion_popup = None
        self.suggestions_visible = False

    async def action_accept_suggestion(self):
        """Accept the selected suggestion."""
        if self.suggestion_popup:
            suggestion = self.suggestion_popup.get_selected_suggestion()
            if suggestion:
                cl = self.cursor_location
                # Assume the matched part don't across lines.
                sl = (cl[0], max(0, cl[1] + suggestion.start_position))
                self.replace(suggestion.text, sl, cl)
        await self.action_hide_suggestions()


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
            input_widget = UserInput(
                input_future,
                history=FileHistory(f".arox.{self.title}.history"),
                suggester=self.app.input_suggester,
            )
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
