import re
from pathlib import Path


def register_tools(manager):
    manager.register(write_to_file)
    manager.register(replace_in_file)


def write_to_file(path: str, content: str) -> str:
    """
    Write content to a file at the specified path. If the file exists, it will be overwritten.
    If the file doesn't exist, it will be created. This tool will automatically create any
    directories needed to write the file.

    Args:
        path: The path of the file to write to.
        content: The complete content to write to the file

    Returns:
        str: Success message or error description
    """
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"


def replace_in_file(path: str, diff: str) -> str:
    """
    Replace sections of content in an existing file using SEARCH/REPLACE blocks.

    Args:
        path: The path of the file to modify.
        diff: One or more SEARCH/REPLACE blocks defining exact changes.
              You can use commentted `...existing code...` to omit some code in *SEARCH* part.
              Except that, the `SEARCH` part should match exactly and clearly, including spaces.
              see DIFF-EXAMPLES.

    DIFF-EXAMPLES:
    example1:

    <<<<<<< SEARCH
    import yaml
    =======
    import json
    >>>>>>> REPLACE

    example2:
    <<<<<<< SEARCH
    import yaml
    # ...existing code...
    from . import foo
    =======
    import json

    from . import bar, foo
    >>>>>>> REPLACE

    Returns:
        str: Success message or error description
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"File not found: {file_path}"

        content = file_path.read_text()
        blocks = diff.split(">>>>>>> REPLACE")

        for block in blocks:
            if not block.strip():
                continue
            parts = block.split("=======")
            if len(parts) < 2:
                continue
            search_part = parts[0].split("<<<<<<< SEARCH")[-1].strip()
            replace_part = parts[1].strip()

            # Check if search_part contains ...existing code...
            m, start_pos, end_pos = _find_with_placeholder(content, search_part)
            if m:
                content = content[:start_pos] + replace_part + content[end_pos:]
            else:
                if search_part in content:
                    content = content.replace(search_part, replace_part, 1)
                else:
                    return f"Search content not found in {file_path}"

        file_path.write_text(content)
        return f"Successfully updated {file_path}"
    except Exception as e:
        return f"Error replacing in file: {str(e)}"


def _find_with_placeholder(content: str, search_pattern: str) -> tuple:
    """
    Find content matching a pattern with ...existing code...
    Returns (matched_text, start_pos, end_pos) or None if not found.
    """
    # Split the search pattern by lines
    lines = search_pattern.split("\n")

    # Find the line that contains ...existing code...
    split_line_index = -1
    for i, line in enumerate(lines):
        if re.search(
            r"^[^a-zA-Z]*" + re.escape("...existing code...") + r"[^a-zA-Z]*$", line
        ):
            split_line_index = i
            break

    if split_line_index == -1:
        return None, None, None

    # Split into before and after parts
    before_lines = lines[:split_line_index]
    after_lines = lines[split_line_index + 1 :]

    # Join the parts back
    before = "\n".join(before_lines).rstrip()
    after = "\n".join(after_lines).lstrip()

    # If either part is empty, handle accordingly
    if not before or not after:
        return None, None, None

    # Both parts exist - find the pattern
    escaped_before = re.escape(before)
    escaped_after = re.escape(after)

    # Create a pattern that matches before...anything...after
    pattern = escaped_before + r".*?" + escaped_after
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return content[match.start() : match.end()], match.start(), match.end()

    return None, None, None
