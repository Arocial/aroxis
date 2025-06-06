import logging

from llmse6.agents.prompt import SimplePromptManager
from llmse6.codebase import project

logger = logging.getLogger(__name__)


class CoderPromptManager(SimplePromptManager):
    def __init__(self, agent):
        super().__init__(agent)
        self.pm = project.ProjectManager(self.workspace)

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        file_contents, chat_files = self.assemble_additional_files()
        repo_map = self.pm.get_repo_map(chat_files)
        input_content = repo_map + file_contents + user_input
        messages.append({"role": "user", "content": input_content})
        logger.debug(f"User Prompt:\n{input_content}")

        return messages
