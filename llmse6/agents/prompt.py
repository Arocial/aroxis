import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SimplePromptManager:
    def __init__(self, agent):
        self.agent = agent
        self.system_prompt = self.agent.system_prompt
        self.messages: List[Dict[str, Any]] = []
        self.workspace = self.agent.workspace
        self.reset()

    def assemble_chat_files(self) -> tuple[str, list[Path]]:
        file_content = ""
        fpaths = []
        chat_files = getattr(self.agent, "chat_files")
        if not chat_files:
            return "", []

        for fname in chat_files.list():
            p = fname if fname.is_absolute() else self.workspace + fname
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
