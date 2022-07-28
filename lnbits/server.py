import click
import uvicorn


@click.command()
@click.option("--port", default="5000", help="Port to run LNBits on")
@click.option("--host", default="127.0.0.1", help="Host to run LNBits on")
def main(port, host):
    """Launched with `poetry run lnbits` at root level"""
    uvicorn.run("lnbits.__main__:app", port=port, host=host)


if __name__ == "__main__":
    main()

# def main():
#    """Launched with `poetry run start` at root level"""
#    uvicorn.run("lnbits.__main__:app")
