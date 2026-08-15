import os
import sys

os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

# Suppress Streamlit email prompt and permission check
from unittest.mock import MagicMock
import streamlit.runtime.credentials as creds
creds.Credentials.get_current = lambda: MagicMock(check_activated=lambda: None)

from streamlit.web import bootstrap

if __name__ == "__main__":
    bootstrap.run(
        "app.py",
        "",
        [],
        flag_options={
            "server.port": 8501,
            "server.headless": True,
            "browser.gatherUsageStats": False,
            "server.address": "0.0.0.0",
        },
    )
