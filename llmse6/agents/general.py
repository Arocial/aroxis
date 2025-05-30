import asyncio

from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.commands import SaveCommand
from llmse6.utils import user_input_generator


class ChatAgent(LLMBaseAgent):
    def __init__(self, name, config_parser=None, local_tool_manager=None):
        super().__init__(name, config_parser, local_tool_manager)
        self.commands.extend([SaveCommand(self)])

    async def start(self, input_gen=None):
        """Start the agent with optional input generator

        Args:
            input_gen: Generator yielding user input strings. If None, uses default generator.
        """
        if input_gen is None:
            input_gen = user_input_generator()

        async with self.tool_registry:
            async for user_input in input_gen:
                if user_input.startswith("/"):
                    command_executed = False
                    for command in self.commands:
                        if command.matches(user_input):
                            # Commands might be async now
                            if asyncio.iscoroutinefunction(command.execute):
                                await command.execute(user_input)
                            else:
                                command.execute(user_input)
                            command_executed = True
                            break
                    if not command_executed:
                        print(f"Command not found: {user_input}")

                    continue

                await self.llm_node(user_input)
