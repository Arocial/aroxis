import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ChatFiles:
    def __init__(self) -> None:
        self._chat_files = []
        self.candidate_generator = None

    def add(self, f: Path):
        self._chat_files.append(f)

    def remove(self, f: Path):
        if f in self._chat_files:
            self._chat_files.remove(f)
        else:
            print(f"{f} is not in chat file list, ignoring.")

    def clear(self):
        self._chat_files.clear()

    def list(self):
        return self._chat_files

    def set_candidate_generator(self, cg):
        self.candidate_generator = cg

    def candidates(self):
        if not self.candidate_generator:
            return []
        return self.candidate_generator()


class SimplePromptManager:
    def __init__(self, agent):
        self.agent = agent
        self.system_prompt = self.agent.system_prompt
        self.messages: List[Dict[str, Any]] = []
        self.workspace = self.agent.workspace
        self.chat_files = ChatFiles()
        self.reset()

    def assemble_chat_files(self) -> tuple[str, list[Path]]:
        file_content = ""
        fpaths = []
        chat_files = self.chat_files
        if not chat_files:
            return "", []

        for fname in chat_files.list():
            p = fname if fname.is_absolute() else self.workspace / fname
            try:
                with open(p, "r") as f:
                    content = f.read()
                    fpaths.append(fname)
                    logger.debug(f"Adding content from {fname}")
                    file_content = (
                        f"\n====FILE:{fname}====\n{content}\n\n{file_content}"
                    )
            except FileNotFoundError:
                print(f"File not found: {p}")
                continue
        return file_content, fpaths

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        file_contents, _ = self.assemble_chat_files()
        user_input = file_contents + user_input
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
