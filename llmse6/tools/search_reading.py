from llmse6.agents.state import SimpleState


class SearchReading:
    def __init__(self, state: SimpleState):
        self.agent_state = state

    def register_tools(self, manager):
        manager.register(self.read_file)

    def read_file(self, path: str):
        """
        Add a file to the chat files for the agent to access.

        Args:
            path: Path to the file to be added to chat context

        Returns:
            str: Success message or error description
        """
        try:
            chat_files = self.agent_state.chat_files
            p = chat_files.normalize(path)
            if not p.exists():
                return "File not exist."

            chat_files.add(p, add_to_new=True)
            return "Successfully added file to context"

        except Exception as e:
            return f"Error reading file: {str(e)}"
