import logging
import uuid
from pathlib import Path

from kissllm.client import LLMClient
from kissllm.mcp import parse_mcp_config
from kissllm.mcp.manager import MCPManager
from kissllm.tools import ToolManager

from arox import utils
from arox.agent_patterns.state import SimpleState

logger = logging.getLogger(__name__)


class LLMBaseAgent:
    def __init__(
        self,
        name,
        config_parser,
        local_tool_manager=None,
        use_flexible_toolcall=True,
        state_cls=SimpleState,
        context={},
        io_channel=None,
    ):
        self.uuid = str(uuid.uuid4())
        self.name = name
        self.context = context
        self.io_channel = io_channel

        self.config_parser = config_parser
        self.config = self.parse_configs()
        # Manage tool specs.
        tool_managers = {}
        self.mcp_servers = (
            self.config.agent.mcp_servers
            if hasattr(self.config.agent, "mcp_servers")
            else None
        )
        if self.mcp_servers:
            mcp_configs = []
            for server_name, server_conf_dict in self.mcp_servers.items():
                mcp_configs.append(parse_mcp_config(server_name, server_conf_dict))
            tool_managers["mcp_manager"] = MCPManager(mcp_configs)
        if local_tool_manager:
            tool_managers["local_manager"] = local_tool_manager

        self.tool_registry = ToolManager(**tool_managers)

        self.state = state_cls(
            self,
            use_flexible_toolcall=use_flexible_toolcall,
            tool_registry=self.tool_registry,
        )

    def set_model(self, model_ref: str):
        self.model_ref = model_ref
        config_parser = self.config_parser
        model_group = config_parser.add_argument_group(name=f"model.'{self.model_ref}'")
        model_group.add_argument("provider_model", default=self.model_ref)
        config_parser.add_argument_group(
            name=f"model.'{self.model_ref}'.params", expose_raw=True
        )
        config = config_parser.parse_args()
        model_config = getattr(config.model, self.model_ref)

        model_params = model_config.params
        self.model_params = utils.deep_merge(self.agent_model_params, model_params)
        self.provider_model = model_config.provider_model
        return config

    async def show_agent_info(self):
        await self.io_channel.write(
            f"Using model {self.provider_model} for {self.name}"
        )

    def parse_configs(self):
        config_parser = self.config_parser
        name = self.name
        agent_group = config_parser.add_argument_group(
            name=f"agent.{name}", expose_raw=True
        )
        agent_group.add_argument("system_prompt", default="")
        agent_group.add_argument("model_ref", default="")
        config_parser.add_argument_group(
            name=f"agent.{name}.model_params", expose_raw=True
        )
        config_parser.add_argument_group(
            name=f"agent.{name}.model_prompt", expose_raw=True
        )
        config = config_parser.parse_args()

        self.workspace = Path(config.workspace)
        if not self.workspace.is_absolute():
            self.workspace = self.workspace.absolute()
        group_config = getattr(config.agent, name)
        self.agent_config = group_config

        # Load default metadata using configargparse
        self.system_prompt = group_config.system_prompt
        self.model_ref = group_config.model_ref or config.model_ref
        self.agent_model_params = group_config.model_params
        self.model_prompt = []
        mp = group_config.model_prompt
        for k, v in mp.items():
            if not k.endswith("_pattern"):
                pattern = mp.get(f"{k}_pattern", "")
                self.model_prompt.append(
                    {
                        "prompt": v,
                        "pattern": pattern,
                    }
                )

        config = self.set_model(self.model_ref)
        return config

    async def _run_before_hooks(self, input_content: str):
        if hasattr(self, "before_step_hooks"):
            for hook in self.before_step_hooks:
                await hook(self, input_content)

    async def _run_after_hooks(self, input_content: str):
        if hasattr(self, "after_step_hooks"):
            for hook in self.after_step_hooks:
                await hook(self, input_content)

    async def step(self, input_content: str):
        await self._run_before_hooks(input_content)
        await self.state.add_user_input(input_content)
        self.model_params["stream"] = True
        await LLMClient(
            provider_model=self.provider_model, io_channel=self.io_channel
        ).async_completion_multi_round(
            state=self.state,
            **self.model_params,
        )
        await self._run_after_hooks(input_content)

    def reset(self):
        return self.state.reset()

    def last_message(self):
        return self.state.last_message()

    def add_before_step_hook(self, hook):
        if not hasattr(self, "before_step_hooks"):
            self.before_step_hooks = []
        self.before_step_hooks.append(hook)

    def add_after_step_hook(self, hook):
        if not hasattr(self, "after_step_hooks"):
            self.after_step_hooks = []
        self.after_step_hooks.append(hook)
