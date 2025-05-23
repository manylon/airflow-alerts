FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


COPY . /app

RUN pip install --upgrade pip && \
    pip install pip-tools


WORKDIR /app/airflow-alerts

RUN pip install .[dev]
