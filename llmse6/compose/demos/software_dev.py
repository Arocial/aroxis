import argparse
import asyncio
from pathlib import Path
import sys

from llmse6.agents.general import ChatAgent
from llmse6.config import TomlConfigParser
from llmse6.utils import user_input_generator


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dump-default-config",
        help="Dump default config to specified file and exit.",
        default="",
    )
    args = parser.parse_args()

    default_agent_config = Path(__file__).parent / "software_dev.toml"
    toml_parser = TomlConfigParser(config_files=[default_agent_config])
    agent = ChatAgent("rewrite", toml_parser)

    if args.dump_default_config:
        with open(args.dump_default_config, "w") as f:
            toml_parser.dump_default_config(f)
        sys.exit(0)

    test_user_msg = [
        f"/add {args.file}",
        "Migrating these files from vue2 to vue3 composition api. only do necessary changes.\n"
        "Output Requirements:\n"
        "1. Don't be lazy: Reply the **whole** migrated file. **Don't omit content even if it is the same with original code.**\n"
        "2. Only output raw migrated code, nothing else, no surrounding ```",
        f"/save {args.file}",
        "q",
    ]
    await agent.start(
        await user_input_generator(
            cached_human_responses=test_user_msg, force_cached=False
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
