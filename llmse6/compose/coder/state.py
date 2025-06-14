import logging

from llmse6.agent_patterns.state import SimpleState
from llmse6.codebase import project

logger = logging.getLogger(__name__)


class CoderState(SimpleState):
    def __init__(self, agent):
        super().__init__(agent)
        self.project_manager = project.ProjectManager(self.workspace)
        self.chat_files.set_candidate_generator(self.project_manager.get_tracked_files)

    def _get_message_items(self, user_input):
        items = super()._get_message_items(user_input)
        if items and items[0][0] == "system_prompt":
            insert_index = 1
        else:
            insert_index = 0
        if not self.message_meta.get("repo_map"):
            chat_files = self.chat_files.list()
            repo_map = self.project_manager.get_repo_map(chat_files)
            items.insert(insert_index, ("repo_map", repo_map))
            self.message_meta["repo_map"] = True
        if not self.message_meta.get("file_list"):
            file_list = "\n".join(self.project_manager.get_tracked_files())
            items.insert(insert_index, ("file_list", file_list))
            self.message_meta["file_list"] = True
        return items
