"""Entry point: uv run python -m attobolt [--dev]"""

import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)

from attobolt.app import main  # noqa: E402

if __name__ == "__main__":
    if "--dev" in sys.argv:
        from pathlib import Path

        from watchfiles import run_process

        from attobolt.app import run_sync

        src_dir = str(Path(__file__).resolve().parent)
        logging.getLogger(__name__).info("Watching %s for changes...", src_dir)
        run_process(src_dir, target=run_sync)
    else:
        asyncio.run(main())
