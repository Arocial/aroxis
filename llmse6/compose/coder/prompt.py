import logging

from llmse6.agents.prompt import SimplePromptManager
from llmse6.codebase import project
from llmse6.utils import xml_wrap

logger = logging.getLogger(__name__)


class CoderPromptManager(SimplePromptManager):
    def __init__(self, agent):
        super().__init__(agent)
        self.project_manager = project.ProjectManager(self.workspace)

    def assemble_prompt(self, user_input: str):
        messages = self.messages
        file_contents, chat_files = self.assemble_chat_files()
        repo_map = self.project_manager.get_repo_map(chat_files)

        input_content = xml_wrap(
            [
                ("repo_map", repo_map),
                ("files", file_contents),
                ("user_instruction", user_input),
            ]
        )

        messages.append({"role": "user", "content": input_content})
        logger.info(f"User Prompt:\n{input_content}")

        return messages
