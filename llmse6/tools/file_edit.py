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
    # ...existing...code
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

            if search_part in content:
                content = content.replace(search_part, replace_part, 1)
            else:
                return f"Search content not found in {file_path}"

        file_path.write_text(content)
        return f"Successfully updated {file_path}"
    except Exception as e:
        return f"Error replacing in file: {str(e)}"
