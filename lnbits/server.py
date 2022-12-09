import uvloop

uvloop.install()

import multiprocessing as mp
import time

import click
import uvicorn

from lnbits.settings import set_cli_settings, settings


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    )
)
@click.option("--port", default=settings.port, help="Port to listen on")
@click.option("--host", default=settings.host, help="Host to run LNBits on")
@click.option(
    "--forwarded-allow-ips",
    default=settings.forwarded_allow_ips,
    help="Allowed proxy servers",
)
@click.option("--ssl-keyfile", default=None, help="Path to SSL keyfile")
@click.option("--ssl-certfile", default=None, help="Path to SSL certificate")
@click.pass_context
def main(
    ctx,
    port: int,
    host: str,
    forwarded_allow_ips: str,
    ssl_keyfile: str,
    ssl_certfile: str,
):
    """Launched with `poetry run lnbits` at root level"""

    set_cli_settings(host=host, port=port, forwarded_allow_ips=forwarded_allow_ips)

    # this beautiful beast parses all command line arguments and passes them to the uvicorn server
    d = dict()
    for a in ctx.args:
        item = a.split("=")
        if len(item) > 1:  # argument like --key=value
            print(a, item)
            d[item[0].strip("--").replace("-", "_")] = (
                int(item[1])  # need to convert to int if it's a number
                if item[1].isdigit()
                else item[1]
            )
        else:
            d[a.strip("--")] = True  # argument like --key

    while True:
        config = uvicorn.Config(
            "lnbits.__main__:app",
            loop="uvloop",
            port=port,
            host=host,
            forwarded_allow_ips=forwarded_allow_ips,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            **d
        )

        server = uvicorn.Server(config=config)
        process = mp.Process(target=server.run)
        process.start()
        server_restart.wait()
        server_restart.clear()
        server.should_exit = True
        server.force_exit = True
        time.sleep(3)
        process.terminate()
        process.join()
        time.sleep(1)


server_restart = mp.Event()

if __name__ == "__main__":
    main()
