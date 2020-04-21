FROM python:3.7

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -q -r requirements.txt
COPY . /app

EXPOSE 5000
