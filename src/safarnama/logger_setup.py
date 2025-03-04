import sys
from loguru import logger


def setup_logger(verbose: bool, save: bool, log_file: str) -> None:
    logger.remove()
    if not verbose and not save:
        logger.disable("crawler")
    else:
        if verbose:
            logger.add(sys.stdout, level="INFO", enqueue=True)
        if save:
            logger.add(log_file, rotation="10 MB", level="INFO", enqueue=True)
