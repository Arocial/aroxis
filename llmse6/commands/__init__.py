class Command:
    """Base class for agent commands"""

    command: str = ""
    description: str = ""

    def __init__(self, agent):
        self.agent = agent

    def matches(self, user_input: str) -> bool:
        """Check if input matches this command"""
        return user_input.startswith(f"/{self.command}")

    def execute(self, user_input: str):
        """Execute command with given input"""
        raise NotImplementedError


class AddCommand(Command):
    command = "add"
    description = "Add files to context - /add <file1> [file2...]"

    def execute(self, user_input: str):
        files = user_input.split()[1:]
        if not files:
            print("Please specify files to add")
            return
        self.agent.additional_files.extend(files)


class ModelCommand(Command):
    command = "model"
    description = "Switch LLM model - /model <model_name>"

    def execute(self, user_input: str):
        parts = user_input.split()
        if len(parts) < 2:
            print("Please specify a model name")
            return
        new_model = parts[1]
        self.agent.provider_model = new_model
        print(f"Switched to model: {new_model}")


class SaveCommand(Command):
    command = "save"
    description = "Save last response - /save [filename] (default: output.md)"

    def __init__(
        self, agent, tag_name: str | None = None, default_file: str = "output.md"
    ):
        super().__init__(agent)
        self.tag_name = tag_name
        self.default_file = default_file

    def execute(self, user_input: str):
        parts = user_input.split()
        output_file = parts[1] if len(parts) > 1 else self.default_file
        last_message = self.agent.state["messages"][-1]
        self.agent._save_content(last_message.content, self.tag_name, output_file)
        print(f"Saved to {output_file}!")
