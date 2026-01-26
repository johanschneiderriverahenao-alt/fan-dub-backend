"""
Test module for pipeline verification.
"""


def greet(name: str) -> str:
    """
    Simple greeting function for testing.

    Args:
        name: The name to greet

    Returns:
        A greeting message
    """
    return f"Hello, {name}!"


def add(num_a: int, num_b: int) -> int:
    """
    Add two numbers.

    Args:
        num_a: First number
        num_b: Second number

    Returns:
        Sum of the two numbers
    """
    return num_a + num_b


if __name__ == "__main__":
    print(greet("World"))
    print(f"2 + 3 = {add(2, 3)}")
