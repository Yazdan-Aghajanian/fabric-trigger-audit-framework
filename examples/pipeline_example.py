"""
Example: Resolve who manually triggered a Fabric Pipeline.

This example must be run inside Microsoft Fabric because the pipeline helper
uses mssparkutils to obtain a Fabric API token.
"""

import os

from src.get_manual_pipeline_triggered_by import get_manual_pipeline_triggered_by
from src.get_graph_display_name_from_upn import get_graph_display_name_from_upn


tenant_id = os.getenv("TENANT_ID", "<TENANT_ID>")
client_id = os.getenv("CLIENT_ID", "<CLIENT_ID>")
client_secret = os.getenv("CLIENT_SECRET", "<CLIENT_SECRET>")

workspace_id = os.getenv("WORKSPACE_ID", "<WORKSPACE_ID>")
pipeline_id = os.getenv("PIPELINE_ID", "<PIPELINE_ID>")
pipeline_run_id = os.getenv("PIPELINE_RUN_ID", "<PIPELINE_RUN_ID>")

audit_triggered_by = get_manual_pipeline_triggered_by(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
    workspace_id=workspace_id,
    pipeline_id=pipeline_id,
    pipeline_run_id=pipeline_run_id,
    window_minutes=15,
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
print("FINAL PIPELINE TRIGGER RESOLUTION")
print("=" * 100)
print("Trigger Type : Manual")
print("Triggered By :", triggered_by)
print("=" * 100)
