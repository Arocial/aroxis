import re
import uuid
from pathlib import Path
from typing import Any, Dict, List

import yaml
from simplellm.client import LLMClient
from typing_extensions import TypedDict

from llmse6 import commands
from llmse6.config import get_config

args = get_config()


class BaseState(TypedDict):
    messages: List[Dict[str, Any]]


class LLMBaseAgent:
    agent_metadata_file = ""

    def __init__(self, global_conf, workspace=None):
        self.global_conf = global_conf
        self.commands = [commands.AddCommand(self), commands.ModelCommand(self)]
        self.llm_model = args.model
        self.uuid = str(uuid.uuid4())
        if workspace is not None:
            self.workspace = Path(workspace)
        else:
            self.workspace = (
                Path(args.workspace) / self.__class__.__name__.lower() / self.uuid
            )
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Load default metadata
        default_metadata_path = args.agent_metadata_path / self.agent_metadata_file

        try:
            with default_metadata_path.open() as agent_yaml:
                default_config = yaml.safe_load(agent_yaml) or {}
        except FileNotFoundError:
            default_config = {}

        # Merge with user-provided metadata from config if exists
        agent_metadata_key = Path(self.agent_metadata_file).stem
        if (
            hasattr(args, "agent_metadata")
            and agent_metadata_key in args.agent_metadata
        ):
            from llmse6.utils import deep_merge

            default_config = deep_merge(
                default_config, args.agent_metadata[agent_metadata_key]
            )

        # Set final config values
        self.system_prompt = default_config.get("system_prompt")
        self.model_params = default_config.get("model_params", {})
        self.provider_model = self.model_params.pop("model", args.model)
        print(f"Using model {self.provider_model} for {agent_metadata_key}")
        self.state = BaseState(messages=[])
        if self.system_prompt:
            self.state["messages"] = [{"role": "system", "content": self.system_prompt}]

        self.additional_files = []

    def llm_node(self, input_content: str):
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
        response = LLMClient(provider_model=self.provider_model).completion(
            messages=messages, **self.model_params
        )

        print(f"======{self.__class__.__name__} Assistant:======")
        for c in response.iter_content():
            print(c, end="", flush=True)
        print()  # Add newline after streaming

        ai_message = response.accumulate_stream()
        self.state["messages"].append(ai_message.choices[0].message)

    def _save_content(self, content_msg: str, tag_name: str | None, file_name: str):
        """Save content from message to file"""
        if tag_name is not None:
            pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
            match = re.search(pattern, content_msg, re.DOTALL)

            if match:
                result = match.group(1)
            else:
                result = content_msg
        else:
            result = content_msg
        output_path = self.workspace / file_name
        print(f"Saving content to {output_path}")
        with output_path.open("w") as f:
            f.write(result)
