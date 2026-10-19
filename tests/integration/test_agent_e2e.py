import pytest

from tests.integration.conftest import requires_gcp


@requires_gcp
@pytest.mark.asyncio(strict=True)
async def test_agent_responds():
    """End-to-end test: create a session, send a message, verify response structure.

    Requires GCP credentials and GOOGLE_CLOUD_PROJECT to be set.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from agents.{{AGENT_NAME_LOWER}}.agent import root_agent

    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="test", session_service=session_service)

    session = await session_service.create_session(app_name="test", user_id="test-user")

    content = types.Content(role="user", parts=[types.Part(text="Hello")])

    events = []
    async for event in runner.run_async(user_id="test-user", session_id=session.id, new_message=content):
        events.append(event)

    assert len(events) > 0
