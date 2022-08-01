import argparse
import uvicorn
from loguru import logger

parser = argparse.ArgumentParser()
parser.add_argument("--port", default="5000", help="Port to run LNBits on")
parser.add_argument("--host", default="127.0.0.1", help="Host to run LNBits on")
def main():
    """Launched with `poetry run lnbits` at root level"""
    args = parser.parse_args()
    logger.debug(args.port)
    uvicorn.run("lnbits.__main__:app", port=args.port, host=args.host)

if __name__ == "__main__":
    main()
