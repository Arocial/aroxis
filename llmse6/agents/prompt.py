import logging
from typing import Any, Dict, List

from llmse6.commands import FileCommand

logger = logging.getLogger(__name__)


class SimplePromptManager:
    def __init__(self, agent):
        self.agent = agent
        self.system_prompt = self.agent.system_prompt
        self.messages: List[Dict[str, Any]] = []
        if self.system_prompt:
            self.messages = [{"role": "system", "content": self.system_prompt}]
        self.workspace = self.agent.workspace
        commands = self.agent.commands
        for c in commands:
            if isinstance(c, FileCommand):
                self.file_command = c
                break
        else:
            self.file_command = None

    def assemble_additional_files(self) -> tuple[str, list[str]]:
        file_content = ""
        file_names = []
        if self.file_command:
            for fname in self.file_command.files:
                p = fname if fname.is_absolute() else self.workspace + fname
                try:
                    with open(p, "r") as f:
                        content = f.read()
                        file_names.append(fname)
                        logger.debug(f"Adding content from {fname}")
                        file_content = (
                            f"\n====FILE:{fname}====\n{content}\n\n{file_content}"
                        )
                except FileNotFoundError:
                    print(f"File not found: {p}")
                    continue
        return file_content, file_names

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        file_contents, _ = self.assemble_additional_files()
        user_input = file_contents + user_input
        messages.append({"role": "user", "content": user_input})

        return messages
