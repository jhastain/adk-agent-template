from agents.{{AGENT_NAME_LOWER}}.agent import root_agent


def test_root_agent_exists():
    assert root_agent is not None


def test_root_agent_name():
    assert root_agent.name == "{{AGENT_NAME_LOWER}}"


def test_root_agent_has_tools():
    assert root_agent.tools is not None
    assert len(root_agent.tools) > 0
