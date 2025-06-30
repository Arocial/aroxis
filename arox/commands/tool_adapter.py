import json
from typing import Any


class ToolAdapter:
    @classmethod
    def parse_str_to_params(cls, func_spec, args_str: str):
        """
        Parse a string of arguments into positional and keyword arguments.

        Args:
            func_spec: Function specification containing parameter information.
            args_str: String of arguments to parse.

        Returns:
            tuple: (args, kwargs) where args is a list of positional arguments
                   and kwargs is a dict of keyword arguments.
        """

        def conv_type(type_str) -> Any:
            if type_str == "string":
                param_type = str
            elif type_str == "integer":
                param_type = int
            elif type_str == "number":
                param_type = float
            elif type_str == "boolean":
                param_type = bool
            elif type_str == "array":
                param_type = list
            else:
                param_type = json.loads
            return param_type

        def parse_param_info(param_info: dict) -> Any:
            type_str = param_info.get("type", "string")
            nargs = None
            param_type = conv_type(type_str)
            if param_type is list:
                nargs = "*"
                param_type = conv_type(param_info.get("items", {}).get("type"))

            argument_params = {"type": param_type}
            if nargs:
                argument_params["nargs"] = nargs
            return argument_params

        import argparse
        import shlex

        parser = argparse.ArgumentParser()

        # Add arguments based on func_spec
        for param_name in func_spec["parameters"]["properties"]:
            param_info = func_spec["parameters"]["properties"][param_name]
            required = param_name in func_spec["parameters"].get("required", [])

            argument_params = parse_param_info(param_info)

            if required:
                # Positional argument for required parameters
                parser.add_argument(
                    param_name,
                    help=param_info.get("description", ""),
                    **argument_params,
                )
            else:
                # Optional argument for non-required parameters
                parser.add_argument(
                    f"--{param_name}",
                    default=None,
                    help=param_info.get("description", ""),
                    **argument_params,
                )

        # Split the args string into a list
        args_list = shlex.split(args_str)

        # Parse the arguments
        parsed_args = parser.parse_args(args_list)

        # Separate positional and keyword arguments
        args = []
        kwargs = {}

        for param_name in func_spec["parameters"]["properties"]:
            value = getattr(parsed_args, param_name)
            if value is not None:
                if param_name in func_spec["parameters"].get("required", []):
                    args.append(value)
                else:
                    kwargs[param_name] = value

        return args, kwargs

    @classmethod
    def parse_output(cls, result):
        print(result)

    @classmethod
    def generate_comand_from_tool(
        cls,
        func,
        command_name=None,
        completion_func=None,
        arg_parser=None,
        output_parser=None,
    ):
        class CommandLike(object):
            pass

        def execute(name: str, args_str: str):
            nonlocal arg_parser, output_parser
            from kissllm.tools import LocalToolManager

            func_spec = LocalToolManager.generate_function_spec(func)
            if arg_parser is None:
                arg_parser = cls.parse_str_to_params
            args, kwargs = arg_parser(func_spec, args_str)
            if output_parser is None:
                output_parser = cls.parse_output
            return output_parser(func(*args, **kwargs))

        def slashes():
            return [command_name or func.__name__]

        def get_completions(*args, **kwargs):
            return []

        command = CommandLike()
        command.slashes = slashes
        command.execute = execute
        command.get_completions = (
            completion_func if completion_func else get_completions
        )

        return command
