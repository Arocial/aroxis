from llmse6 import commands
from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.agents.prompt import SimplePromptManager
from llmse6.utils import user_input_generator


class ChatAgent(LLMBaseAgent):
    def __init__(
        self,
        name,
        config_parser=None,
        local_tool_manager=None,
        prompt_manager_cls=SimplePromptManager,
    ):
        super().__init__(name, config_parser, local_tool_manager, prompt_manager_cls)

        self.additional_files = []
        self.register_in_chat_command(commands.FileCommand(self))
        self.register_in_chat_command(commands.ModelCommand(self))
        self.register_in_chat_command(commands.InvokeToolCommand(self))
        self.register_in_chat_command(commands.ListToolCommand(self))
        self.register_in_chat_command(commands.SaveCommand(self))

    async def start(self, input_gen=None):
        """Start the agent with optional input generator

        Args:
            input_gen: Generator yielding user input strings. If None, uses default generator.
        """
        if input_gen is None:
            input_gen = user_input_generator()

        async with self.tool_registry:
            async for user_input in input_gen:
                if not user_input.strip():
                    continue
                is_command = await self.try_execute_command(user_input)
                if not is_command:
                    await self.llm_node(user_input)
