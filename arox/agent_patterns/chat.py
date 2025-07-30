from arox import commands
from arox.agent_patterns.llm_base import LLMBaseAgent
from arox.agent_patterns.state import SimpleState
from arox.commands.manager import CommandManager


class ChatAgent(LLMBaseAgent):
    def __init__(
        self,
        name,
        config_parser=None,
        local_tool_manager=None,
        use_flexible_toolcall=True,
        state_cls=SimpleState,
        context={},
        io_channel=None,
    ):
        super().__init__(
            name,
            config_parser,
            local_tool_manager,
            use_flexible_toolcall,
            state_cls,
            context=context,
            io_channel=io_channel,
        )

        self.command_manager = CommandManager(self)

    def register_commands(self, cmds: list[commands.Command]):
        self.command_manager.register_commands(cmds)

    async def start(self):
        """Start the agent with optional input generator"""
        async with self.tool_registry:
            async for user_input in self.io_channel.read():
                if not user_input.strip():
                    continue
                is_command = await self.command_manager.try_execute_command(user_input)
                if not is_command:
                    await self.step(user_input)
