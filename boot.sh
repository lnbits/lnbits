#!/bin/sh
pipenv run flask migrate

exec pipenv run gunicorn -b :5000 -w 1--access-logfile - --error-logfile - lnbits:app
