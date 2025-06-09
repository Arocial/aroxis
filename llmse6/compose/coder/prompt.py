import logging

from llmse6.agents.prompt import SimplePromptManager
from llmse6.codebase import project

logger = logging.getLogger(__name__)


class CoderPromptManager(SimplePromptManager):
    def __init__(self, agent):
        super().__init__(agent)
        self.pm = project.ProjectManager(self.workspace)

    def _xml_wrap(self, tag, content):
        if content:
            return f"<{tag}>\n{content}\n</{tag}>\n\n"
        else:
            return ""

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        file_contents, chat_files = self.assemble_additional_files()
        repo_map = self.pm.get_repo_map(chat_files)

        input_content = (
            self._xml_wrap("repo_map", repo_map)
            + self._xml_wrap("files", file_contents)
            + self._xml_wrap("user_instruction", user_input)
        )
        messages.append({"role": "user", "content": input_content})
        logger.info(f"User Prompt:\n{input_content}")

        return messages
