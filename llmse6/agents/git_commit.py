import subprocess
from typing import Optional

from llmse6.agents.llm_base import LLMBaseAgent


class GitCommitAgent(LLMBaseAgent):
    """
    An agent that generates commit messages based on git diff output.
    """

    def __init__(self, name: str, config_parser=None, local_tool_manager=None):
        super().__init__(name, config_parser, local_tool_manager)

    async def generate_commit_message(self, diff: Optional[str] = None) -> str:
        """
        Generate a commit message based on the provided git diff or the current changes.

        Args:
            diff: Optional git diff string. If None, the current changes are fetched.

        Returns:
            str: The generated commit message.
        """
        if diff is None:
            # Fetch the current changes using git diff
            try:
                diff = subprocess.check_output(
                    ["git", "diff", "--staged"],
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
            except subprocess.CalledProcessError as e:
                return f"Error fetching git diff: {e.stderr}"

        if not diff:
            return "No changes detected to generate a commit message."

        # Use the LLM to generate a commit message based on the diff
        prompt = (
            "Generate ONE concise and meaningful commit message based on the following git diff. "
            "Respond with ONLY commit message.\n\n"
            f"{diff}"
        )

        # Call the LLM to generate the commit message
        await self.llm_node(prompt)
        last_message = self.prompt_manger.messages[-1]["content"]
        return last_message.strip()

    async def commit_changes(self, message: Optional[str] = None) -> str:
        """
        Commit the staged changes with the provided or generated commit message.

        Args:
            message: Optional commit message. If None, a message is generated.

        Returns:
            str: The output of the git commit command or an error message.
        """
        if message is None:
            message = await self.generate_commit_message()

        try:
            output = subprocess.check_output(
                ["git", "commit", "-m", message],
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            return output
        except subprocess.CalledProcessError as e:
            return f"Error committing changes: {e.stderr}"

    async def auto_commit_changes(self) -> str:
        """
        Automatically commit any uncommitted changes with a generated commit message.
        This includes both staged and unstaged changes.

        Returns:
            str: The output of the git commit command or an error message.
        """
        # Stage all unstaged changes
        try:
            subprocess.check_output(
                ["git", "add", "."],
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        except subprocess.CalledProcessError as e:
            return f"Error staging changes: {e.stderr}"

        # Check for staged changes
        try:
            diff = subprocess.check_output(
                ["git", "diff", "--staged"],
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            if not diff:
                return "No changes detected to commit."

            # Generate and commit the changes
            message = await self.generate_commit_message(diff)
            return await self.commit_changes(message)
        except subprocess.CalledProcessError as e:
            return f"Error checking for changes: {e.stderr}"


if __name__ == "__main__":
    import asyncio

    from llmse6 import agents
    from llmse6.config import TomlConfigParser

    toml_parser = TomlConfigParser()
    agents.init(toml_parser)

    async def main():
        agent = GitCommitAgent("git_commit_agent", toml_parser)
        result = await agent.auto_commit_changes()
        print(result)

    asyncio.run(main())
