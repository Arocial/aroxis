from arox import commands
from arox.agent_patterns.llm_base import LLMBaseAgent
from arox.agent_patterns.state import SimpleState
from arox.commands.manager import CommandManager
from arox.utils import user_input_generator


class ChatAgent(LLMBaseAgent):
    def __init__(
        self,
        name,
        config_parser=None,
        local_tool_manager=None,
        use_flexible_toolcall=True,
        state_cls=SimpleState,
        context={},
    ):
        super().__init__(
            name,
            config_parser,
            local_tool_manager,
            use_flexible_toolcall,
            state_cls,
            context=context,
        )

        self.command_manager = CommandManager(self)

    def register_commands(self, cmds: list[commands.Command]):
        self.command_manager.register_commands(cmds)

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
                is_command = await self.command_manager.try_execute_command(user_input)
                if not is_command:
                    await self.step(user_input)
