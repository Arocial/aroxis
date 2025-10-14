import logging

import git

logger = logging.getLogger(__name__)


class ProjectManager:
    def __init__(self, worksapce, agent):
        self.workspace = worksapce
        self.agent = agent

    def get_tracked_files(self):
        try:
            repo = git.Repo(self.workspace)
            tracked_files = repo.git.ls_files().splitlines()
            return sorted(tracked_files)
        except (git.InvalidGitRepositoryError, git.GitCommandError) as e:
            logger.debug(f"Failed to get git tracked files: {e}")
            return []
