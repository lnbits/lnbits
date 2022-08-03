import uvicorn
from lnbits.settings import HOST, PORT


def main():
    """Launched with `poetry run lnbits` at root level"""
    config = uvicorn.Config("lnbits.__main__:app", port=PORT, host=HOST)
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
