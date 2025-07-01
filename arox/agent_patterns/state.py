import logging
from pathlib import Path
from typing import Any, Dict, List

from kissllm.client import DefaultResponseHandler
from kissllm.stream import CompletionStream

from arox.utils import xml_wrap

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

    def add_by_names(self, paths: list[str]):
        succeed = []
        not_exist = []
        for path in paths:
            p = self.normalize(path)
            if not p.exists():
                not_exist.append(path)
                continue
            self.add(p)
            succeed.append(path)
        return {"succeed": succeed, "not_exist": not_exist}

    def add(self, f: Path):
        if f not in self._chat_files:
            self._chat_files.append(f)
        if f not in self._pending_files:
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

    def have_pending(self):
        return bool(self._pending_files)

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
        if not self._chat_files:
            return "", []

        # This is intended to check self._pending_files but add self._chat_files.
        for fname in self._chat_files:
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
        if not messages_meta.get("system"):
            items.append(("system", self.system_prompt))
            self.message_meta["system"] = True
        if self.chat_files.have_pending() or user_input:
            file_contents, _ = self.assemble_chat_files()
            items.append(("files", file_contents))
        if user_input:
            items.append(("user_instruction", user_input))
        return items

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        items = self._get_message_items(user_input)
        has_new = bool(items)
        for item in items:
            if item[0] == "system":
                messages.append({"role": "system", "content": item[1]})
                continue
            content = xml_wrap([item])
            # remove all outdated file contents and append updated.
            if item[0] == "files":
                messages = [msg for msg in messages
                            if not msg.get("content", "").strip().startswith("<files>")]
            if content:
                messages.append({"role": "user", "content": content})

        return messages, has_new

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
            print(
                "\n======WARNING: Escape characters might be displayed incorrectly======\n"
            )
            last_character = ""
            async for content in response.iter_content():
                if not content:
                    continue
                if last_character == "\\":
                    content = "\b \b\\" + content
                print(
                    content.replace(r"\n", "\n")
                    .replace(r"\"", '"')
                    .replace("\\\\", "\\"),
                    end="",
                    flush=True,
                )
                last_character = content[-1]
            print("\n")
        return await super().accumulate_response(response)

    async def __call__(self, response):
        messages, continu = await super().__call__(response)
        messages, new_content = self.state.assemble_prompt("")

        return messages, new_content and continu
