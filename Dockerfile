FROM python:3.12-slim

WORKDIR app

RUN pip install pytest

COPY . .

