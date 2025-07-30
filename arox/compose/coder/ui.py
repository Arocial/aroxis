from arox.compose.coder.main import CoderComposer
from arox.ui import TUIByIO


class CoderTUI(TUIByIO):
    def on_mount(self) -> None:
        composer = CoderComposer(self)
        self.run_worker(composer.run, name="composer", exclusive=True)
