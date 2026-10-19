from agents.{{AGENT_NAME_LOWER}}.tools import example_tool


def test_example_tool_returns_string():
    result = example_tool("hello")
    assert isinstance(result, str)


def test_example_tool_includes_input():
    result = example_tool("test input")
    assert "test input" in result
