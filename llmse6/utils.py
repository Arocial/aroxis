import yaml
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory


def deep_merge(source, overrides):
    """Deep merge two dictionaries, with overrides taking precedence"""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source:
            source[key] = deep_merge(source.get(key, {}), value)
        else:
            source[key] = value
    return source


def parse_dict(value: str) -> dict:
    """Parse a string of key=value pairs into a dictionary"""
    if not value.strip():
        return {}
    return dict(yaml.safe_load(value))


def user_input_generator(
    cached_human_responses=[], cached_response_index=0, force_cached=False
):
    """Generator that yields user input"""

    def wrapper():
        nonlocal cached_response_index
        while True:
            try:
                history = FileHistory(".llmse6_history")
                if force_cached:
                    user_input = cached_human_responses[cached_response_index]
                    cached_response_index += 1
                    print(f"(cached): {user_input}\n")
                else:
                    user_input = prompt(
                        "User (q/Q to quit): ",
                        history=history,
                        auto_suggest=AutoSuggestFromHistory(),
                        mouse_support=False,
                    )
            except EOFError:
                user_input = cached_human_responses[cached_response_index]
                cached_response_index += 1
                print(f"(cached): {user_input}\n")
            if user_input in {"q", "Q"}:
                print("AI: Byebye")
                return
            yield user_input

    return wrapper()
