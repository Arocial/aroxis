import pytest

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


def test_user_input_generator_cached():
    cached_responses = ["test1", "test2"]
    gen = user_input_generator(cached_responses)
    assert next(gen) == "test1"
    assert next(gen) == "test2"


def test_user_input_generator_quit():
    gen = user_input_generator(["q"])
    with pytest.raises(StopIteration):
        next(gen)


@pytest.mark.parametrize(
    "input,expected",
    [
        (["test"], "test"),
        (["Q"], StopIteration),
        (["q"], StopIteration),
        (["test1", "test2"], "test1"),
        (["test1", "q"], "test1"),
    ],
)
def test_user_input_generator_parametrized(input, expected):
    gen = user_input_generator(input)
    if expected is StopIteration:
        with pytest.raises(StopIteration):
            next(gen)
    else:
        assert next(gen) == expected


def test_user_input_generator_multiple_calls():
    gen = user_input_generator(["test1", "test2", "q"])
    assert next(gen) == "test1"
    assert next(gen) == "test2"
    with pytest.raises(StopIteration):
        next(gen)
