from llmse6 import agents
from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.commands import SaveCommand
from llmse6.utils import user_input_generator


class PrdAgent(LLMBaseAgent):
    agent_metadata_file = "prd.yaml"

    def __init__(self, global_conf, workspace=None):
        super().__init__(global_conf, workspace=workspace)
        self.commands.extend(
            [SaveCommand(self, tag_name="prd_content", default_file="prd.md")]
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
    global_conf = agents.init()
    agent = PrdAgent(global_conf, workspace="workspace/test/")
    test_user_msg = [
        "请设计一个手电筒App，可以调节亮度。",
        "只实现核心功能，选择你认为合适的方案，直接给出PRD。",
        "/save",
        "q",
    ]
    agent.start(user_input_generator(cached_human_responses=test_user_msg))
