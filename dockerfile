FROM python:3.13-slim

WORKDIR /app

COPY ./requirements.txt /app/requirements.txzt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./ /app