"""
Example: Resolve who manually triggered a standalone Fabric Notebook.

In a production Fabric notebook, notebook_start_time_utc should come from
the current notebook job instance metadata.
"""

import os

from src.get_manual_notebook_triggered_by import get_manual_notebook_triggered_by
from src.get_graph_display_name_from_upn import get_graph_display_name_from_upn


tenant_id = os.getenv("TENANT_ID", "<TENANT_ID>")
client_id = os.getenv("CLIENT_ID", "<CLIENT_ID>")
client_secret = os.getenv("CLIENT_SECRET", "<CLIENT_SECRET>")

workspace_id = os.getenv("WORKSPACE_ID", "<WORKSPACE_ID>")
notebook_id = os.getenv("NOTEBOOK_ID", "<NOTEBOOK_ID>")
notebook_start_time_utc = os.getenv(
    "NOTEBOOK_START_TIME_UTC",
    "2026-01-01T00:00:00Z"
)

audit_triggered_by = get_manual_notebook_triggered_by(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
    workspace_id=workspace_id,
    notebook_id=notebook_id,
    notebook_start_time_utc=notebook_start_time_utc,
    window_minutes=15,
    max_allowed_time_diff_seconds=60,
    retry_count=10,
    retry_interval_seconds=60
)

triggered_by = get_graph_display_name_from_upn(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
    upn=audit_triggered_by
)

print("\n" + "=" * 100)
print("FINAL NOTEBOOK TRIGGER RESOLUTION")
print("=" * 100)
print("Trigger Type : Manual")
print("Triggered By :", triggered_by)
print("=" * 100)
