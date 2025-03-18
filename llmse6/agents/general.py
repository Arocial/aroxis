from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.commands import SaveCommand
from llmse6.utils import user_input_generator


class ChatAgent(LLMBaseAgent):
    def __init__(self, name, config_parser=None):
        super().__init__(name, config_parser)
        self.commands.extend(
            [SaveCommand(self, tag_name=None, default_file="output.md")]
        )

    async def start(self, input_gen=None):
        """Start the agent with optional input generator

        Args:
            input_gen: Generator yielding user input strings. If None, uses default generator.
        """
        if input_gen is None:
            input_gen = user_input_generator()

        async for user_input in input_gen:
            command_executed = False
            for command in self.commands:
                if command.matches(user_input):
                    command.execute(user_input)
                    command_executed = True
                    break
            if command_executed:
                continue

            await self.llm_node(user_input)
