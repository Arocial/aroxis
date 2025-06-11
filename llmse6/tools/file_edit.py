import logging
import re
from pathlib import Path

from llmse6.agents.llm_base import LLMBaseAgent
from llmse6.utils import xml_wrap

logger = logging.getLogger(__name__)


class FileEdit:
    def __init__(self, diff_agent: LLMBaseAgent):
        self.diff_agent = diff_agent

    def register_tools(self, manager):
        manager.register(self.write_to_file)
        manager.register(self.replace_in_file)

    async def _apply_smart_diff(self, original_content: str, diff: str) -> str:
        logger.info("Trying to use smart diff to apply changes.")
        if not self.diff_agent:
            return ""
        prompt = xml_wrap([("original_content", original_content), ("diff", diff)])
        await self.diff_agent.llm_node(prompt)
        return self.diff_agent.last_message()

    def _match_placeholder(self, content):
        return re.search(
            r"^[^a-zA-Z]*" + re.escape("...existing code...") + r"[^a-zA-Z]*$",
            content,
            re.MULTILINE,
        )

    async def write_to_file(self, path: str, content: str) -> str:
        """
        Write content to a file at the specified path. If the file exists, it will be overwritten.
        If the file doesn't exist, it will be created. This tool will automatically create any
        directories needed to write the file.

        Args:
            path: The path of the file to write to.
            content: The complete content to write to the file. You can use commentted `...existing code...` to omit code. see CONTENT_EXAMPLES.

        CONTENT_EXAMPLES:

        import json
        import yaml
        # ...existing code...
        class TestClass:
            # ...existing code...

        Returns:
            str: Success message or error description
        """
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if self._match_placeholder(content):
                original_content = file_path.read_text()
                content = await self._apply_smart_diff(original_content, content)
            file_path.write_text(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing to file: {str(e)}"

    async def replace_in_file(self, path: str, diff: str) -> str:
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
            blocks = diff.split("\n>>>>>>> REPLACE")

            for block in blocks:
                if not block.strip():
                    continue
                parts = block.split("\n=======\n")
                if len(parts) < 2:
                    continue
                search_part = parts[0].split("<<<<<<< SEARCH\n")[-1]
                replace_part = parts[1]

                # Check if search_part contains ...existing code...
                m, start_pos, end_pos = self._find_with_placeholder(
                    content, search_part
                )
                if m:
                    content = content[:start_pos] + replace_part + content[end_pos:]
                else:
                    if search_part in content:
                        content = content.replace(search_part, replace_part, 1)
                    else:
                        content = await self._apply_smart_diff(content, diff)

            file_path.write_text(content)
            return f"Successfully updated {file_path}"
        except Exception as e:
            return f"Error replacing in file: {str(e)}"

    def _find_with_placeholder(self, content: str, search_pattern: str) -> tuple:
        """
        Find content matching a pattern with ...existing code...
        Returns (matched_text, start_pos, end_pos) or None if not found.
        """
        m = self._match_placeholder(search_pattern)
        if not m:
            return None, None, None

        before = search_pattern[: m.start() - 1]
        after = search_pattern[m.end() + 1 :]

        # If either part is empty, handle accordingly
        if not before or not after:
            return None, None, None

        escaped_before = re.escape(before)
        escaped_after = re.escape(after)

        # Create a pattern that matches before...anything...after
        pattern = escaped_before + r".*?" + escaped_after
        match = re.search(pattern, content, re.DOTALL)

        if match:
            return content[match.start() : match.end()], match.start(), match.end()

        return None, None, None
