def example_tool(query: str) -> str:
    """An example tool that echoes the input. Replace with your actual tools.

    ADK auto-generates tool schemas from:
    - Function name -> tool identifier
    - Docstring -> tool description for the LLM
    - Type hints -> parameter types
    - Default values -> optional vs required

    Args:
        query: The input to process.

    Returns:
        A response string. ADK requires string or dict returns.
    """
    return f"Processed: {query}"
