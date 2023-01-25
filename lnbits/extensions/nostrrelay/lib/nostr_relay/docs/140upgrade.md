# Upgrading to 1.4.0

1.4.0 switches to sqlalchemy for data access, and modifies the schema to be more normalized.

You must change your configuration file from:

```
db_filename = /path/to/db.sqlite3
```

to:

```
storage:
  sqlalchemy.url: sqlite+aiosqlite:///path/to/db.sqlite3
```

(See [storage](storage.md) for more options)

Initial migration should happen automatically on server restart, but you will have to run a re-verification process if nip-05 verification is enabled:

```nostr-relay -c config.yaml reverify```

