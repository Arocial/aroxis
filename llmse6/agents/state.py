import logging
from pathlib import Path
from typing import Any, Dict, List

from kissllm.client import DefaultResponseHandler
from kissllm.stream import CompletionStream

from llmse6.utils import xml_wrap

logger = logging.getLogger(__name__)


class ChatFiles:
    def __init__(self, workspace) -> None:
        self._chat_files = []
        self._pending_files = []
        self.candidate_generator = None
        self.workspace = workspace

    def normalize(self, path: str) -> Path:
        workspace = self.workspace
        # normalize file path to relative to workspace if it's subtree of workspace, otherwise absolute.
        p = Path(path)
        if not p.is_absolute():
            p = (workspace / p).absolute()
        if p.is_relative_to(workspace):
            p = p.relative_to(workspace)
        return p

    def add(self, f: Path):
        self._chat_files.append(f)
        self._pending_files.append(f)

    def remove(self, f: Path):
        if f in self._chat_files:
            self._chat_files.remove(f)
        else:
            print(f"{f} is not in chat file list, ignoring.")

        if f in self._pending_files:
            self._pending_files.remove(f)

    def clear(self):
        self._pending_files.clear()
        self._chat_files.clear()

    def clear_pending(self):
        self._pending_files.clear()

    def list(self):
        return self._chat_files

    def set_candidate_generator(self, cg):
        self.candidate_generator = cg

    def candidates(self):
        if not self.candidate_generator:
            return []
        return self.candidate_generator()

    def read_files(self):
        file_content = ""
        fpaths = []
        files = self._pending_files
        if not files:
            return "", []

        for fname in files:
            p = fname if fname.is_absolute() else self.workspace / fname
            try:
                with open(p, "r") as f:
                    content = f.read()
                    fpaths.append(fname)
                    logger.debug(f"Adding content from {fname}")
                    file_content = (
                        f"\n====FILE: {fname}====\n{content}\n\n{file_content}"
                    )
            except FileNotFoundError:
                print(f"File not found: {p}")
                continue

        self.clear_pending()
        return file_content, fpaths


class SimpleState:
    def __init__(self, agent):
        self.agent = agent
        self.system_prompt = self.agent.system_prompt
        self.messages: List[Dict[str, Any]] = []
        self.message_meta = {}
        self.workspace = self.agent.workspace
        self.chat_files = ChatFiles(self.workspace)
        self.response_handler = ResponseHandler(self)
        self.reset()

    def assemble_chat_files(self) -> tuple[str, list[Path]]:
        return self.chat_files.read_files()

    def _get_message_items(self, user_input):
        items = []
        messages_meta = self.message_meta
        if not messages_meta.get("system_prompt"):
            items.append(("system_prompt", self.system_prompt))
            self.message_meta["system_prompt"] = True
        file_contents, _ = self.assemble_chat_files()
        if file_contents:
            items.append(("files", file_contents))
        if user_input:
            items.append(("user_instruction", user_input))
        return items

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        items = self._get_message_items(user_input)
        content = xml_wrap(items)

        if content:
            messages.append({"role": "user", "content": content})
            return messages, True
        return messages, False

    def last_message(self) -> str:
        if self.messages and "content" in self.messages[-1]:
            return self.messages[-1]["content"]
        else:
            return ""

    def reset(self):
        self.chat_files.clear()


class ResponseHandler(DefaultResponseHandler):
    def __init__(self, state: SimpleState):
        super().__init__(state.messages)
        self.state = state

    async def accumulate_response(self, response):
        if isinstance(response, CompletionStream):
            print("\n======Streaming Assistant Response:======")
            async for content in response.iter_content():
                print(content.replace(r"\n", "\n"), end="", flush=True)
            print("\n")
        return await super().accumulate_response(response)

    async def __call__(self, response):
        messages, continu = await super().__call__(response)
        messages, new_content = self.state.assemble_prompt("")

        return messages, new_content and continu
