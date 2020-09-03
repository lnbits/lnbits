FROM python:3.8-slim

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -q -r requirements.txt
RUN pip install --no-cache-dir -q gunicorn gevent
COPY . /app

EXPOSE 5000
