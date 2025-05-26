# airflow-alerts

**airflow-alerts** is a Python library that provides reusable, configurable alerting utilities for [Apache Airflow](https://airflow.apache.org/).  
Easily send notifications to Google Chat and other channels from your Airflow DAGs with minimal setup.

## Features

- Plug-and-play alert callbacks for Airflow tasks and DAGs
- Google Chat integration out of the box

## Installation Instructions

This package is not available on PyPI.  
Install directly from the repository:
```sh
pip install git+https://github.com/manylon/airflow-alerts.git#subdirectory=airflow-alerts
```

## Usage

1. **Create a Connection in Airflow:**
    - Go to **Admin → Connections** in the Airflow UI.
    - Click **+** to add a new connection.
    - Set **Conn Type** to `Generic`.
    - Enter your Google Chat webhook URL in the **Password** field.
    - Set **Conn Id** (e.g., `my_gchat_conn`).

2. **Send Alerts from Your Task:**

```python
from airflow_alerts.google_chat import task_success_alert

# In your DAG definition
on_success_callback = task_success_alert("my_gchat_conn")
```

This will send a Google Chat notification when the task succeeds, using the webhook URL stored in your Airflow connection.

### Google Chat Notifications

- **Task Success**: Use `task_success_alert(conn_id)` to notify a Google Chat room when a task completes successfully.
- **Task Failure**: Use `task_failure_alert(conn_id)` to alert your team in Google Chat if a task fails.
To use these notification functions, simply import and assign them as callbacks in your DAG or task definition. See the usage examples above for details.

Additional integrations and notification channels may be added in the future. Contributions are welcome!
