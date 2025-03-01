from llmse6 import agents
from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.commands import SaveCommand
from llmse6.utils import user_input_generator


class GeneralAgent(LLMBaseAgent):
    agent_metadata_file = "general.yaml"

    def __init__(self, global_conf, workspace=None):
        super().__init__(global_conf, workspace=workspace)
        self.commands.extend(
            [SaveCommand(self, tag_name=None, default_file="output.md")]
        )

    def start(self, input_gen=None):
        """Start the agent with optional input generator

        Args:
            input_gen: Generator yielding user input strings. If None, uses default generator.
        """
        if input_gen is None:
            input_gen = user_input_generator()

        for user_input in input_gen:
            command_executed = False
            for command in self.commands:
                if command.matches(user_input):
                    command.execute(user_input)
                    command_executed = True
                    break
            if command_executed:
                continue

            self.llm_node(user_input)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace", help="Workspace directory path", default="workspace/test/"
    )
    args = parser.parse_args()

    global_conf = agents.init()
    agent = GeneralAgent(global_conf, workspace=args.workspace)
    test_user_msg = [
        "q",
    ]
    agent.start(user_input_generator(cached_human_responses=test_user_msg))
