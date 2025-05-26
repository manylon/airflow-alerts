import json
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from enum import Enum

from airflow.hooks.base import BaseHook

from .utils import (
    _build_task_log_url,
    _build_task_run_id,
    _ensure_https,
    _get_dag_run_identifiers,
    _get_redis_client,
    _send_post_request,
    _validate_url,
)


class STATUS_COLORS(Enum):
    """Enum for Google Chat message colors."""

    success = {"red": 0.8, "green": 1, "blue": 0.8}
    failure = {"red": 1, "green": 0.8, "blue": 0.8}
    default = {"red": 0.95, "green": 0.95, "blue": 0.95}
    retry = {"red": 1, "green": 0.9, "blue": 0.7}
    skipped = {"red": 0.9, "green": 0.8, "blue": 1}
    sla_miss = {"red": 1, "green": 0.85, "blue": 0.85}


def _construct_webhook_url(connection_id: str, run_id: str = ""):
    """
    Constructs the webhook URL for the specified connection ID.
    Args:
        connection_id (str): The connection ID.
        run_id (str): The optional thread reference. TODO fix this
    Returns:
        str: The constructed URL.
    """
    gchat_connection = BaseHook.get_connection(connection_id)
    # Reference for Google Chat API:
    # https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create
    # MessageReplyOption details:
    # https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create#MessageReplyOption
    thread_ref = (
        f"&thread_key={run_id}&messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
    )
    full_url = f"{gchat_connection.password}{thread_ref}"
    return full_url


def _send_message(dag_id, run_id, connection_id, message_body):
    run_id = _build_task_run_id(dag_id, run_id)
    full_url = _ensure_https(_construct_webhook_url(connection_id, run_id))
    if not _validate_url(full_url):
        print(f"Invalid URL: {full_url}")
        return
    print("Sending message to Google Chat")
    return _send_post_request(message_body, full_url)


def basic_alert(
    connection_id: str, message_body: dict, redis_conn_id: str = None, delay: dt_time = None
):
    """
    Sends a basic alert to Google Chat.
    Useful to send small informative messages in working hours to stakeholders.
    Args:
        connection_id (str): The connection ID.
        message_body (str): The message body.
        redis_conn_id (str): The Redis connection ID. If None, the alert is sent immediately.
        delay (dt_time): The time to delay the alert. If None, the alert is sent immediately.
    """

    def basic_alert_inner(context):
        dag_id, run_id = _get_dag_run_identifiers(context)
        if delay and redis_conn_id:
            redis_conn = _get_redis_client(redis_conn_id)
            now = datetime.now()
            target = now.replace(
                hour=delay.hour, minute=delay.minute, second=delay.second, microsecond=0
            )
            if target <= now:
                target += timedelta(days=1)
            # Prepare alert data
            alert_data = {
                "dag_id": dag_id,
                "run_id": run_id,
                "connection_id": connection_id,
                "message_body": message_body,
            }
            # Store in Redis sorted set with target timestamp as score
            redis_conn.zadd(
                "scheduled_alerts", {json.dumps(alert_data): target.timestamp()}
            )
            print(f"Alert scheduled for {target.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            return _send_message(dag_id, run_id, connection_id, message_body)

    return basic_alert_inner


def task_success_alert(connection_id: str, redis_conn_id: str = None, delay: dt_time = None):
    """
    Sends a task success alert to Google Chat.
    Args:
        connection_id (str): The connection ID.
    """

    def task_success_alert_inner(context):
        task_instance = context.get("task_instance")
        task_log_url = _build_task_log_url(task_instance)
        # For more details on the message format, refer to the Google Chat API documentation:
        # https://developers.google.com/chat/api/guides/message-formats/cards
        # https://developers.google.com/workspace/chat/api/reference/rest/v1/cards
        message_body = {
            "cardsV2": [
                {
                    "cardId": "airflow-task-success",
                    "card": {
                        "header": {
                            "title": "✅ Task completed successfully!",
                        },
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "decoratedText": {
                                            "topLabel": "Task Name",
                                            "text": f"<b>{task_instance.task.task_display_name}</b>",
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Task Description",
                                            "text": task_instance.task.doc_md,
                                            "wrapText": True,
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "DAG ID",
                                            "text": str(task_instance.dag_id),
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Hostname",
                                            "text": str(task_instance.hostname),
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Execution Date",
                                            "text": task_instance.start_date.strftime(
                                                "%Y-%m-%d %H:%M:%S"
                                            ),
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Execution number / Max executions",
                                            "text": f"{task_instance.try_number} / {task_instance.max_tries + 1}",
                                        }
                                    },
                                    {
                                        "buttonList": {
                                            "buttons": [
                                                {
                                                    "text": "<b>View Logs</b>",
                                                    "color": STATUS_COLORS.success.value,
                                                    "onClick": {
                                                        "openLink": {
                                                            "url": task_log_url
                                                        }
                                                    },
                                                }
                                            ]
                                        }
                                    },
                                ]
                            }
                        ],
                    },
                }
            ]
        }
        return basic_alert(
            connection_id=connection_id,
            message_body=message_body,
            redis_conn_id=redis_conn_id,
            delay=delay
        )(context)

    return task_success_alert_inner


def task_failure_alert(connection_id: str, redis_conn_id: str = None, delay: dt_time = None):
    """
    Sends a task failure alert to Google Chat.
    Args:
        connection_id (str): The connection ID.
    """

    def task_failure_alert_inner(context):
        task_instance = context.get("task_instance")
        task_log_url = _build_task_log_url(task_instance)
        # For more details on the message format, refer to the Google Chat API documentation:
        # https://developers.google.com/chat/api/guides/message-formats/cards
        # https://developers.google.com/workspace/chat/api/reference/rest/v1/cards
        message_body = {
            "cardsV2": [
                {
                    "cardId": "airflow-task-success",
                    "card": {
                        "header": {
                            "title": "❌ Task failed!",
                        },
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "decoratedText": {
                                            "topLabel": "Task Name",
                                            "text": f"<b>{task_instance.task.task_display_name}</b>",
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Task Description",
                                            "text": task_instance.task.doc_md,
                                            "wrapText": True,
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "DAG ID",
                                            "text": str(task_instance.dag_id),
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Hostname",
                                            "text": str(task_instance.hostname),
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Execution Date",
                                            "text": task_instance.start_date.strftime(
                                                "%Y-%m-%d %H:%M:%S"
                                            ),
                                        }
                                    },
                                    {
                                        "decoratedText": {
                                            "topLabel": "Execution number / Max executions",
                                            "text": f"{task_instance.try_number} / {task_instance.max_tries + 1}",
                                        }
                                    },
                                    {
                                        "buttonList": {
                                            "buttons": [
                                                {
                                                    "text": "<b>View Logs</b>",
                                                    "color": STATUS_COLORS.failure.value,
                                                    "onClick": {
                                                        "openLink": {
                                                            "url": task_log_url
                                                        }
                                                    },
                                                }
                                            ]
                                        }
                                    },
                                ]
                            }
                        ],
                    },
                }
            ]
        }
        return basic_alert(
            connection_id=connection_id,
            message_body=message_body,
            redis_conn_id=redis_conn_id,
            delay=delay
        )(context)

    return task_failure_alert_inner
