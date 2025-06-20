import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from llmse6.utils import deep_merge, user_input_generator


def test_deep_merge_basic():
    source = {"a": 1, "b": {"c": 2}}
    overrides = {"b": {"c": 3, "d": 4}, "e": 5}
    result = deep_merge(source, overrides)
    assert result == {"a": 1, "b": {"c": 3, "d": 4}, "e": 5}


def test_deep_merge_empty_source():
    source = {}
    overrides = {"a": 1, "b": {"c": 2}}
    result = deep_merge(source, overrides)
    assert result == {"a": 1, "b": {"c": 2}}


def test_deep_merge_empty_overrides():
    source = {"a": 1, "b": {"c": 2}}
    overrides = {}
    result = deep_merge(source, overrides)
    assert result == {"a": 1, "b": {"c": 2}}


def test_deep_merge_nested_structures():
    source = {"a": {"b": {"c": 1}}, "d": [1, 2]}
    overrides = {"a": {"b": {"c": 2}}, "d": [3, 4]}
    result = deep_merge(source, overrides)
    assert result == {"a": {"b": {"c": 2}}, "d": [3, 4]}


@pytest.mark.asyncio
async def test_user_input_generator_quit():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("test1\n")
        pipe_input.send_text("q\n")

        gen = user_input_generator(
            input=pipe_input,
            output=DummyOutput(),
        )

        assert await anext(gen) == "test1"
        with pytest.raises(StopAsyncIteration):
            await anext(gen)
