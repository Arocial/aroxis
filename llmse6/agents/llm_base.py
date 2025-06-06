import logging
import uuid
from pathlib import Path

from kissllm.client import LLMClient
from kissllm.mcp import (
    SSEMCPConfig,
    StdioMCPConfig,
)
from kissllm.mcp.manager import MCPManager
from kissllm.tools import ToolManager

from llmse6 import commands
from llmse6.agents.prompt import SimplePromptManager
from llmse6.commands import InvokeToolCommand, ListToolCommand

logger = logging.getLogger(__name__)


class LLMBaseAgent:
    def __init__(
        self,
        name,
        config_parser,
        local_tool_manager=None,
        prompt_manager_cls=SimplePromptManager,
    ):
        self.uuid = str(uuid.uuid4())
        self.name = name

        agent_group = config_parser.add_argument_group(name=f"agent.{name}")
        agent_group.add_argument("system_prompt", default="")
        config_parser.add_argument_group(
            name=f"agent.{name}.model_params", expose_raw=True
        )
        config = config_parser.parse_args()
        self.config = config

        self.workspace = Path(config.workspace)
        group_config = getattr(config.agent, name)

        # Load default metadata using configargparse
        self.system_prompt = group_config.system_prompt
        self.model_params = group_config.model_params
        self.provider_model = self.model_params.pop("model", config.model)
        print(f"Using model {self.provider_model} for {name}")

        # Manage tool specs.
        tool_managers = {}
        self.mcp_servers = (
            config.agent.mcp_servers if hasattr(config.agent, "mcp_servers") else None
        )
        if self.mcp_servers:
            mcp_configs = []
            for server_name, server_conf_dict in self.mcp_servers.items():
                if "command" in server_conf_dict:
                    mcp_configs.append(
                        StdioMCPConfig(name=server_name, **server_conf_dict)
                    )
                elif "url" in server_conf_dict:
                    mcp_configs.append(
                        SSEMCPConfig(name=server_name, **server_conf_dict)
                    )
                else:
                    logger.warning(
                        f"Skipping MCP server '{server_name}': Configuration must contain 'command' (for stdio) or 'url' (for sse)."
                    )
                    continue
            tool_managers["mcp_manager"] = MCPManager(mcp_configs)
        if local_tool_manager:
            tool_managers["local_manager"] = local_tool_manager
        if tool_managers:
            self.tool_registry = ToolManager(**tool_managers)
        else:
            self.tool_registry = None

        self.commands = [
            commands.FileCommand(self),
            commands.ModelCommand(self),
            InvokeToolCommand(self),
            ListToolCommand(self),
        ]
        self.prompt_manger = prompt_manager_cls(self)

    async def llm_node(self, input_content: str):
        messages = self.prompt_manger.assemble_prompt(input_content)
        self.model_params["stream"] = True
        await LLMClient(
            provider_model=self.provider_model, tool_registry=self.tool_registry
        ).async_completion_with_tool_execution(
            messages=messages, msg_update=list.append, **self.model_params
        )
