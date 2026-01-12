"""
Pytest configuration and fixtures for agent tests.
"""
import pytest
import sys
import os

# Ensure the lib directory is in the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))


@pytest.fixture
def sample_text():
    """Fixture providing sample text for testing."""
    return "This is a sample text for testing token counting."


@pytest.fixture
def large_text():
    """Fixture providing large text for testing."""
    return " ".join(["word"] * 1000)


@pytest.fixture
def code_snippet():
    """Fixture providing a code snippet for testing."""
    return '''
def example_function(param1, param2):
    """Example function docstring."""
    result = param1 + param2
    return result
'''


@pytest.fixture
def multiline_text():
    """Fixture providing multiline text for testing."""
    return "\n".join([f"Line {i}: Some content here" for i in range(50)])
