import logging
from pathlib import Path

import git

from . import repomap

logger = logging.getLogger(__name__)


class ProjectManager:
    def __init__(self, worksapce):
        self.workspace = worksapce

    def get_repo_map(self, chat_files_p: list[Path]) -> str:
        rm = repomap.RepoMap(root=self.workspace)
        other_files = self.calcute_other_files(chat_files_p)
        chat_files = [str(f) for f in chat_files_p]
        logger.debug(
            f"Files to generate repomap: \n"
            f"chat files: {chat_files}\n"
            f"other files: {other_files}"
        )
        res = rm.get_repo_map(chat_files, other_files)
        return res or ""

    def calcute_other_files(self, chat_files):
        tracked_files = set(self.get_tracked_files())
        other_files = tracked_files - set(chat_files)
        return list(other_files)

    def get_tracked_files(self):
        try:
            repo = git.Repo(self.workspace)
            tracked_files = repo.git.ls_files().splitlines()
            return sorted(tracked_files)
        except (git.InvalidGitRepositoryError, git.GitCommandError) as e:
            logger.debug(f"Failed to get git tracked files: {e}")
            return []
