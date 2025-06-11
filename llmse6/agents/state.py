import logging
from pathlib import Path
from typing import Any, Dict, List

from kissllm.client import default_handle_response

from llmse6.utils import xml_wrap

logger = logging.getLogger(__name__)


class ChatFiles:
    def __init__(self, workspace) -> None:
        self._chat_files = []
        self.candidate_generator = None
        self.workspace = workspace
        self._new_files = []

    def normalize(self, path: str) -> Path:
        workspace = self.workspace
        # normalize file path to relative to workspace if it's subtree of workspace, otherwise absolute.
        p = Path(path)
        if not p.is_absolute():
            p = (workspace / p).absolute()
        if p.is_relative_to(workspace):
            p = p.relative_to(workspace)
        return p

    def add(self, f: Path, add_to_new=False):
        self._chat_files.append(f)
        if add_to_new:
            self._new_files.append(f)

    def remove(self, f: Path):
        if f in self._chat_files:
            self._chat_files.remove(f)
        else:
            print(f"{f} is not in chat file list, ignoring.")

    def clear(self, only_new=False):
        self._new_files.clear()
        if not only_new:
            self._chat_files.clear()

    def list(self):
        return self._chat_files

    def set_candidate_generator(self, cg):
        self.candidate_generator = cg

    def candidates(self):
        if not self.candidate_generator:
            return []
        return self.candidate_generator()

    def read_files(self, only_new=False):
        file_content = ""
        fpaths = []
        files = self._new_files if only_new else self._chat_files
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
        return file_content, fpaths


class SimpleState:
    def __init__(self, agent):
        self.agent = agent
        self.system_prompt = self.agent.system_prompt
        self.messages: List[Dict[str, Any]] = []
        self.workspace = self.agent.workspace
        self.chat_files = ChatFiles(self.workspace)
        self.reset()

    def assemble_chat_files(self) -> tuple[str, list[Path]]:
        return self.chat_files.read_files()

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        file_contents, _ = self.assemble_chat_files()
        user_input = xml_wrap(
            [
                ("files", file_contents),
                ("user_instruction", user_input),
            ]
        )
        messages.append({"role": "user", "content": user_input})

        return messages

    def last_message(self) -> str:
        if self.messages and "content" in self.messages[-1]:
            return self.messages[-1]["content"]
        else:
            return ""

    def reset(self):
        if self.system_prompt:
            self.messages = [{"role": "system", "content": self.system_prompt}]
        self.chat_files.clear()

    async def handle_response(self, response, message):
        messages, have_tool_call = await default_handle_response(response, message)
        file_contents, _ = self.chat_files.read_files(only_new=True)
        if file_contents:
            messages.append(
                {"role": "user", "content": xml_wrap([("files", file_contents)])}
            )
        self.chat_files.clear(only_new=True)

        return messages, have_tool_call
