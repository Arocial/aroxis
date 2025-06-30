import argparse
import asyncio
import sys
from pathlib import Path

from arox import agent_patterns
from arox.agent_patterns.chat import ChatAgent
from arox.config import TomlConfigParser
from arox.utils import user_input_generator


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
    agent_patterns.init(toml_parser)
    prd_agent = ChatAgent("prd", toml_parser)
    ux_agent = ChatAgent("ux", toml_parser)

    if args.dump_default_config:
        with open(args.dump_default_config, "w") as f:
            toml_parser.dump_default_config(f)
        sys.exit(0)

    test_user_msg = []
    await prd_agent.start(user_input_generator(cached_human_responses=test_user_msg))

    print("PRD agent finished.")

    await ux_agent.start(user_input_generator())


if __name__ == "__main__":
    asyncio.run(main())
