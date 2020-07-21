FROM python:3.7

RUN adduser --disabled-login lnbits

WORKDIR /home/lnbits

COPY Pipfile.lock Pipfile.lock
COPY Pipfile Pipfile

ARG FLASK_ENV
COPY pipenv-install.sh pipenv-install.sh
RUN chmod +x pipenv-install.sh && ./pipenv-install.sh

COPY . /home/lnbits

COPY boot.sh ./
RUN chmod +x boot.sh

RUN chown -R lnbits:lnbits ./
USER lnbits

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
