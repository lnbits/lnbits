import multiprocessing as mp
import time
from pathlib import Path

import click
import uvicorn
import uvloop
from uvicorn.supervisors import ChangeReload

from lnbits.settings import set_cli_settings, settings

uvloop.install()


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

    # create data dir if it does not exist
    Path(settings.lnbits_data_folder).mkdir(parents=True, exist_ok=True)

    # create extension dir if it does not exist
    Path(settings.lnbits_path, "extensions").mkdir(parents=True, exist_ok=True)

    set_cli_settings(host=host, port=port, forwarded_allow_ips=forwarded_allow_ips)

    # this beautiful beast parses all command line arguments and
    # passes them to the uvicorn server
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

        if config.should_reload:
            sock = config.bind_socket()
            run = ChangeReload(config, target=server.run, sockets=[sock]).run
        else:
            run = server.run

        process = mp.Process(target=run)
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
