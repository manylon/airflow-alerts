import os
from urllib.parse import urlparse

import redis
import requests
from airflow.hooks.base import BaseHook


def _ensure_https(full_url: str) -> str:
    """
    Ensures that the given URL uses HTTPS.
    Args:
        full_url (str): The URL to check.
    Returns:
        str: The URL with HTTPS scheme if it was not already.
    """
    parsed_url = urlparse(full_url)
    if parsed_url.scheme != "https":
        full_url = parsed_url._replace(scheme="https").geturl()
    return full_url


def _validate_url(full_url: str) -> bool:
    """
    Validates a given URL.
    Args:
        full_url (str): The URL to validate.
    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    try:
        result = urlparse(full_url)
        return all([result.scheme, result.netloc])
    except AttributeError:
        return False


def _send_post_request(message_body, full_url):
    """
    Sends a POST request to the specified URL with the given message body.
    Args:
        message_body (dict): The message body to send.
        full_url (str): The URL to send the request to.
    Returns:
        int: The HTTP status code of the response.
    """
    r = requests.post(
        url=full_url,
        json=message_body,
        headers={"Content-type": "application/json"},
    )
    if r.status_code != 200:
        print(f"Error: {r.status_code} - {r.text}")
        print("Failed to send message.")
    else:
        print("Message sent successfully!")
    return r.status_code


def _build_task_log_url(task_instance) -> str:
    """
    Constructs the task log URL for the given task instance.
    Args:
        task_instance (TaskInstance): The task instance.
    Returns:
        str: The constructed task log URL.
    """
    base_url = os.environ.get("AIRFLOW__API__BASE_URL", "http://localhost:8080")
    if "local" not in base_url:
        base_url = _ensure_https(base_url)
    task_url = f"{base_url}/dags/{task_instance.dag_id}/runs/{task_instance.run_id}/tasks/{task_instance.task_id}"
    return task_url


def _get_redis_client(connection_id="redis_default"):
    """
    Returns a Redis client using Airflow connection.
    Args:
        connection_id (str): The Airflow connection ID for Redis.
    Returns:
        redis.Redis: Redis client instance.
    """
    conn = BaseHook.get_connection(connection_id)
    return redis.Redis(
        host=conn.host,
        port=conn.port or 6379,
        db=int(conn.schema or 0),
        password=conn.password or None,
    )


def _build_task_run_id(dag_id, run_id) -> str:
    """
    Constructs a unique task run ID based on the context.
    Args:
        context (dict): The context dictionary.
    Returns:
        str: The constructed task run ID.
    """
    dag_id = str(dag_id)
    run_id = str(run_id).replace("+", "-").replace(":", "-")
    return f"{dag_id}-{run_id}"


def _get_dag_run_identifiers(context) -> tuple:
    """
    Extracts the DAG ID and run ID from the context.
    Args:
        context (dict): The context dictionary.
    Returns:
        tuple: A tuple containing the DAG ID and run ID.
    """
    task_instance = context.get("task_instance")
    dag_id = str(task_instance.dag_id)
    run_id = str(task_instance.run_id)
    return dag_id, run_id
