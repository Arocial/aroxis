from llmse6.agent_patterns.state import SimpleState


class SearchReading:
    def __init__(self, state: SimpleState):
        self.agent_state = state

    def register_tools(self, manager):
        manager.register(self.read_files)

    def read_files(self, paths: list[str]):
        """
        Add multiple files to the chat files for the agent to access.

        Args:
            paths: List of paths to files to be added to chat context

        Returns:
            str: Success message or error description
        """
        try:
            chat_files = self.agent_state.chat_files
            results = []
            for path in paths:
                p = chat_files.normalize(path)
                if not p.exists():
                    results.append(f"File not exist: {path}")
                    continue
                chat_files.add(p)
                results.append(f"Successfully added file: {path}")

            return "\n".join(results)

        except Exception as e:
            return f"Error reading files: {str(e)}"
