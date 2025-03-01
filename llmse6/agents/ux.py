from pathlib import Path

from llmse6 import agents
from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.commands import SaveCommand
from llmse6.utils import user_input_generator


class UXPromptAgent(LLMBaseAgent):
    agent_metadata_file = "ux.yaml"

    def __init__(self, global_conf, prd_input=None, workspace=None):
        super().__init__(global_conf, workspace=workspace)
        self.commands.extend(
            [SaveCommand(self, tag_name="ux_content", default_file="ux_prompts.md")]
        )
        self.prd_input = prd_input

    def start(self, input_gen=None):
        """Start the agent with optional input generator

        Args:
            input_gen: Generator yielding user input strings. If None, uses default generator.
        """
        if input_gen is None:
            input_gen = user_input_generator()

        if self.prd_input:
            prd_path = Path(self.prd_input)
            if prd_path.is_file():
                with prd_path.open() as f:
                    prd_content = f.read()
            else:
                prd_content = self.prd_input
        else:
            prd_content = ""

        # First process PRD content
        if self.prd_input:
            print(f"Processing PRD:\n{prd_content}")
            self.llm_node(prd_content)

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
    workspace = "workspace/test"
    prd_input = workspace + "/prd.md"
    test_user_msg = [
        "请按你认为好的方案进行设计",
        "/save",
        "q",
    ]
    agent = UXPromptAgent(global_conf, prd_input, workspace=workspace)
    agent.start(user_input_generator(cached_human_responses=test_user_msg))
