import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SimplePromptManager:
    def __init__(self, agent):
        self.agent = agent
        self.system_prompt = self.agent.system_prompt
        self.messages: List[Dict[str, Any]] = []
        if self.system_prompt:
            self.messages = [{"role": "system", "content": self.system_prompt}]
        self.workspace = self.agent.workspace

    def assemble_additional_files(self) -> tuple[str, list[Path]]:
        file_content = ""
        fpaths = []
        additional_files = getattr(self.agent, "additional_files", [])
        for fname in additional_files:
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
        file_contents, _ = self.assemble_additional_files()
        user_input = file_contents + user_input
        messages.append({"role": "user", "content": user_input})

        return messages
