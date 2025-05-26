import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from airflow.decorators import task
from airflow_alerts.google_chat import _construct_webhook_url

from airflow import DAG


@task
def simple_task():
    """
    ### Simple Task
    This is a simple task that does nothing but serves as a placeholder.
    """
    print("Task executed successfully!")


@task
def task_that_fails():
    """ """
    raise Exception("This task is designed to fail.")


def test_construct_webhook_url():
    mock_conn = MagicMock()
    mock_conn.password = "https://gchat.example/webhook"
    with patch(
        "airflow_alerts.google_chat.BaseHook.get_connection", return_value=mock_conn
    ):
        url = _construct_webhook_url("my_conn", run_id="abc123")
        assert url.startswith("https://gchat.example/webhook")
        assert "thread_key=abc123" in url
        assert "messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD" in url

    # Test with no run_id
    with patch(
        "airflow_alerts.google_chat.BaseHook.get_connection", return_value=mock_conn
    ):
        url = _construct_webhook_url("my_conn")
        assert url.startswith("https://gchat.example/webhook")
        assert "thread_key=" in url
        assert "messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD" in url


def test__build_task_run_id():
    from airflow_alerts.google_chat import _build_task_run_id

    assert (
        _build_task_run_id("my_dag", "2023-10-01T00:00:00+00:00")
        == "my_dag-2023-10-01T00-00-00-00-00"
    )


def test_basic_alert():
    from airflow_alerts.google_chat import basic_alert

    mock_conn = MagicMock()
    mock_conn.password = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")

    with patch(
        "airflow_alerts.google_chat.BaseHook.get_connection", return_value=mock_conn
    ), patch(
        "airflow_alerts.google_chat._get_dag_run_identifiers",
        return_value=("my_dag", "abc123"),
    ):

        alert_fn = basic_alert(
            connection_id="my_conn", message_body={"text": "This is a test alert"}
        )
        result = alert_fn(context={})
        assert result == 200


def test_task_success_alert():
    from airflow_alerts.google_chat import task_success_alert

    mock_conn = MagicMock()
    mock_conn.password = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")
    mock_task = simple_task()
    mock_task.task_display_name = "Test Task"
    mock_task.doc_md = "Task description"
    mock_task_instance = MagicMock()
    mock_task_instance.task = mock_task
    mock_task_instance.dag_id = "my_dag"
    mock_task_instance.hostname = "test-host"
    mock_task_instance.start_date = datetime(2024, 5, 26, 12, 0, 0)
    mock_task_instance.try_number = 1
    mock_task_instance.max_tries = 2
    context = {
        "task_instance": mock_task_instance,
        "dag": DAG(
            "my_dag", start_date=datetime(2024, 5, 26), schedule=timedelta(days=1)
        ),
    }

    with patch(
        "airflow_alerts.google_chat.BaseHook.get_connection", return_value=mock_conn
    ), patch(
        "airflow_alerts.google_chat._get_dag_run_identifiers",
        return_value=("my_dag", "abc123"),
    ), patch(
        "airflow_alerts.google_chat._build_task_log_url",
        return_value="http://example.com/logs",
    ):

        alert_fn = task_success_alert(connection_id="my_conn")

        result = alert_fn(context=context)

        assert result == 200


def test_task_failure_alert():
    from airflow_alerts.google_chat import task_failure_alert

    mock_conn = MagicMock()
    mock_conn.password = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")
    mock_task = task_that_fails()
    mock_task.task_display_name = "Test Task"
    mock_task.doc_md = "Task description"
    mock_task_instance = MagicMock()
    mock_task_instance.task = mock_task
    mock_task_instance.dag_id = "my_dag"
    mock_task_instance.hostname = "test-host"
    mock_task_instance.start_date = datetime(2024, 5, 26, 12, 0, 0)
    mock_task_instance.try_number = 1
    mock_task_instance.max_tries = 2
    context = {
        "task_instance": mock_task_instance,
        "dag": DAG(
            "my_dag", start_date=datetime(2024, 5, 26), schedule=timedelta(days=1)
        ),
    }

    with patch(
        "airflow_alerts.google_chat.BaseHook.get_connection", return_value=mock_conn
    ), patch(
        "airflow_alerts.google_chat._get_dag_run_identifiers",
        return_value=("my_dag", "abc123"),
    ), patch(
        "airflow_alerts.google_chat._build_task_log_url",
        return_value="http://example.com/logs",
    ):

        alert_fn = task_failure_alert(connection_id="my_conn")

        result = alert_fn(context=context)

        assert result == 200
