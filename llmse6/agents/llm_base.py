import uuid
from pathlib import Path
from typing import Any, Dict, List

from kissllm.client import LLMClient
from typing_extensions import TypedDict

from llmse6 import commands


class BaseState(TypedDict):
    messages: List[Dict[str, Any]]


class LLMBaseAgent:
    def __init__(self, name, config_parser):
        agent_group = config_parser.add_argument_group(name=f"agent.{name}")
        agent_group.add_argument("system_prompt", default="")
        config_parser.add_argument_group(
            name=f"agent.{name}.model_params", expose_raw=True
        )
        config = config_parser.parse_args()

        self.commands = [commands.AddCommand(self), commands.ModelCommand(self)]
        self.uuid = str(uuid.uuid4())
        self.name = name

        self.workspace = Path(config.workspace)
        group_config = getattr(config.agent, name)

        # Load default metadata using configargparse
        self.system_prompt = group_config.system_prompt
        self.model_params = group_config.model_params
        self.provider_model = self.model_params.pop("model", config.model)
        print(f"Using model {self.provider_model} for {name}")
        self.state = BaseState(messages=[])
        if self.system_prompt:
            self.state["messages"] = [{"role": "system", "content": self.system_prompt}]

        self.additional_files = []

    async def llm_node(self, input_content: str):
        messages = self.state["messages"]

        for fname in self.additional_files:
            try:
                with open(self.workspace / fname, "r") as f:
                    content = f.read()
                    print(f"Adding content from {fname}")
                    input_content = f"{fname}:\n{content}\n{input_content}"
            except FileNotFoundError:
                print(f"File not found: {fname}")
                continue

        messages.append({"role": "user", "content": input_content})

        self.model_params["stream"] = True
        response = await LLMClient(provider_model=self.provider_model).async_completion(
            messages=messages, **self.model_params
        )

        print(f"======{self.__class__.__name__} Assistant:======")
        async for c in response.iter_content():
            print(c, end="", flush=True)
        print()  # Add newline after streaming

        ai_message = await response.accumulate_stream()
        self.state["messages"].append(ai_message.choices[0].message)
