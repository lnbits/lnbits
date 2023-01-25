import asyncio
import click
from functools import wraps
from .web import run_with_gunicorn
from .config import Config


def async_cmd(func):
  @wraps(func)
  def wrapper(*args, **kwargs):
    return asyncio.run(func(*args, **kwargs))
  return wrapper


@click.group()
@click.option('--config', '-c', required=False, help="Config file")
@click.pass_context
def main(ctx, config):
    ctx.ensure_object(dict)

    Config.load(config)


@main.command()
@click.pass_context
def serve(ctx):
    """
    Start the http relay server 
    """
    import os.path
    from alembic import config
    alembic_config_file = os.path.join(os.path.dirname(__file__), "alembic.ini")
    config.main([f'-c{alembic_config_file}', 'upgrade', 'head'])

    run_with_gunicorn()


@main.command()
@click.option("--identifier", '-i', help="Identifier (name@domain)")
@click.option("--pubkey", '-p', help="Public key")
@click.option("--relay", '-r', multiple=True, help='Relay address (can be added multiple times)')
@click.pass_context
@async_cmd
async def adduser(ctx, identifier='', pubkey='', relay=None):
    """
    Add a user to the NIP-05 identity table
    """
    if not identifier:
        click.echo("Identifier required")
    else:
        click.echo(f'Adding {identifier} = {pubkey} with relays: {relay}')

        from .storage import get_storage
        async with get_storage() as storage:
            await storage.set_identified_pubkey(identifier, pubkey, relays=relay)


@main.command()
@click.option("--query", '-q', help="Query", prompt="Enter REQ filters")
@click.option('--results/--no-results', default=True)
@click.pass_context
@async_cmd
async def query(ctx, query, results):
    """
    Run a REQ query and display results
    """
    import rapidjson
    from .storage import get_storage
    from .storage.db import Subscription
    if not query:
        click.echo("query is required")
        return -1
    query = query.strip()
    if not query.startswith('['):
        query = f'[{query}]'
    query = rapidjson.loads(query)
    queue = asyncio.Queue()
    async with get_storage() as storage:
        sub = Subscription(storage.db, 'cli', query, queue=queue, default_limit=60000, log=storage.log, is_postgres=storage.is_postgres)
        sub.prepare()
        click.echo(click.style('Query:', bold=True))
        click.echo(click.style(sub.query, fg="green"))
        await sub.run_query()

    if results:
        click.echo(click.style('Results:', fg='black', bold=True))

        while True:
            sub, event = await queue.get()
            if event:
                click.echo(click.style(rapidjson.dumps(event.to_json_object(), indent=4), fg="red"))
                click.echo('')
            else:
                break


@main.command()
@click.option("--event/--no-event", '-e', help="Return as EVENT message JSON", default=True)
@click.pass_context
@async_cmd
async def dump(ctx, event):
    """
    Dump all events
    """
    query = [{'since': 1}]
    as_event = event
    from .db import get_storage
    async with get_storage() as storage:
        async for event_json in storage.run_single_query(query):
            if as_event:
                print(f'["EVENT", {event_json}]')
            else:
                print(event_json)


@main.command()
@click.option("--query", '-q', help="Query", prompt="Enter REQ filters", default='[{"since": 1}]')
@click.pass_context
@async_cmd
async def update_tags(ctx, query):
    """
    Update the tags in the tag table, from a REQ query
    """
    from .storage import get_storage

    if not query:
        query = '[{"since": 1}]'

    query = rapidjson.loads(query)

    async with get_storage() as storage:
        count = 0
        async with storage.db.begin() as cursor:
            async for event in storage.run_single_query(query):
                await storage.process_tags(cursor, event)
                count += 1

        click.echo("Processed %d events" % count)


@main.command()
@click.pass_context
@async_cmd
async def reverify(ctx):
    """
    Reverify all NIP-05 metadata events
    """
    from .storage import get_storage
    from rapidjson import loads

    async with get_storage() as storage:
        count = 0
        async with storage.db.begin() as cursor:
            async for event in storage.run_single_query([{'kinds': [0]}]):
                meta = loads(event.content)
                if 'nip05' in meta:
                    await storage.verifier.verify(cursor, event)
                    count += 1

        click.echo("Found %d events" % count)
        if count:
            while storage.verifier.is_processing():
                await asyncio.sleep(1)


@main.command()
@click.option("--event/--no-event", '-e', help="Return as EVENT message JSON", default=True)
@click.pass_context
@async_cmd
async def dump(ctx, event):
    """
    Dump all events
    """
    query = [{'since': 1}]
    as_event = event
    from .storage import get_storage
    async with get_storage() as storage:
        async for event_json in storage.run_single_query(query):
            if as_event:
                print(f'["EVENT", {event_json}]')
            else:
                print(event_json)


@main.command
@click.argument("filename", required=False)
@click.pass_context
@async_cmd
async def load(ctx, filename):
    """
    Load events
    """
    import sys
    if filename:
        fileobj = open(filename, 'r')
    else:
        fileobj = sys.stdin
    import collections
    from rapidjson import loads

    Config.authentication['enabled'] = False
    # this will reverify profiles but not reject unverified events
    if Config.verification['nip05_verification'] == 'enabled':
        Config.verification['nip05_verification'] = 'passive'

    Config.oldest_event = 315360000

    from .storage import get_storage
    from .errors import StorageError
    kinds = collections.defaultdict(int)
    count = 0
    async with get_storage() as storage:
        await storage.verifier.stop()
        while fileobj:
            line = fileobj.readline()
            if not line:
                break
            js = loads(line)
            if isinstance(js, list):
                event = js[1]
            else:
                event = js
            try:
                event, added = await storage.add_event(event)
            except StorageError as e:
                print(f'Error: {e} for {event}')
                added = False
            if added:
                kinds[event.kind] += 1
                count += 1
            if count and count % 500 == 0:
                click.echo(f"Added {count} events...")
    fileobj.close()
    click.echo("\nTotal events:")
    for kind, num in sorted(kinds.items()):
        click.echo(f"\tkind-{kind}: {num}")
    click.echo(f"total: {count}")



@click.group()
@click.pass_context
def role(ctx):
    """
    View/Set authentication roles
    """
    pass


@role.command()
@click.option('--pubkey', '-p', help='Public Key', default='')
@click.option('--roles', '-r', help='Roles', default='')
@async_cmd
async def set(pubkey, roles):
    """
    Set roles in the authentication table
    """
    from .storage import get_storage

    if not pubkey:
        click.echo('public key is required')
        return -1

    async with get_storage() as storage:
        await storage.authenticator.set_roles(pubkey, roles)
        click.echo(f"Set roles for pubkey: {pubkey} to {roles}")


@role.command()
@click.option('--pubkey', '-p', help='Public Key', default='')
@async_cmd
async def get(pubkey):
    """
    Get roles from the authentication table
    """
    from .storage import get_storage
    async with get_storage() as storage:
        if not pubkey:
            async for pubkey, role in storage.authenticator.get_all_roles():
                click.echo(f'{pubkey}: {role}')
        else:
            roles = await storage.authenticator.get_roles(pubkey)
            click.echo(roles)

main.add_command(role)


@main.command()
@click.option('--ids', help='ids')
@click.option('--authors', help='authors')
@click.option('--kinds', help='kinds')
@click.option('--etags', help='etags')
@click.option('--ptags', help='ptags')
@click.option('--since', help='since')
@click.option('--until', help='until')
@click.option('--limit', help='limit')
@click.option('--source', help='source relay', default='ws://localhost:6969')
@click.option('--target', help='to relay', default='ws://localhost:6969')
def mirror(ids, authors, kinds, etags, ptags, since, until, limit, source, target):
    """
    Mirror REQ from source relay(s) to target relay(s)

    (this just calls the commands: nostreq, jq, and nostcat, which must exist on the PATH)
    """
    cmd = ['nostreq']
    if ids:
        cmd.append(f'--ids {ids}')
    if authors:
        cmd.append(f'--authors {authors}')
    if kinds:
        cmd.append(f'--kinds {kinds}')
    if etags:
        cmd.append(f'--etags {etags}')
    if ptags:
        cmd.append(f'--ptags {ptags}')
    if since:
        cmd.append(f'--since {since}')
    if until:
        cmd.append(f'--until {until}')
    if limit:
        cmd.append(f'--limit {limit}')

    cmd.append('|')
    cmd.append("nostcat")
    cmd.extend(source.split(','))
    cmd.append('|')
    cmd.append("jq -c 'del(.[1])'")
    cmd.append('|')
    cmd.append("nostcat --stream")
    cmd.extend(target.split(','))

    command = ' '.join(cmd)
    print(command)
    import subprocess, sys
    proc = subprocess.Popen(command, shell=True, bufsize=0, stdout=sys.stdout, stderr=subprocess.PIPE)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.kill()
        return 0


@main.command(context_settings=dict(
    ignore_unknown_options=True,
))
@click.argument('alembic_args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def alembic(ctx, alembic_args):
    import os.path
    from alembic import config
    alembic_args = (f'-c{os.path.join(os.path.dirname(__file__), "alembic.ini")}', ) + alembic_args
    return config.main(alembic_args)

