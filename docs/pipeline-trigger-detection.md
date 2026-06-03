# Pipeline Trigger Detection

## Overview

Pipeline trigger detection resolves who manually triggered a Microsoft Fabric Pipeline run.

The pipeline implementation uses the exact pipeline run identifier to first resolve the real run start time. It then searches the Power BI / Fabric Admin Activity Events API for a matching audit event.

## Flow

```text
Pipeline Run ID
      │
      ▼
Fabric queryactivityruns API
      │
      ▼
Actual Pipeline Run Start Time
      │
      ▼
Admin Activity Events API
      │
      ▼
RunArtifact Event
      │
      ▼
UserId / UPN
      │
      ▼
Microsoft Graph Display Name Lookup
```

## Matching Logic

The audit event is matched by:

```text
Operation = RunArtifact
ObjectId  = pipeline_id
```

The audit log does not directly expose the Fabric pipeline run ID. Therefore, the framework uses:

```text
Pipeline ID + RunArtifact + closest CreationTime
```

## Retry Logic

Admin Activity Events API records may not always be visible immediately. The function supports retry settings:

```python
retry_count=10
retry_interval_seconds=60
```

For most pipeline runs, the audit event appears quickly. The retry loop is included to make the implementation more reliable.

## Example Output

```text
Trigger Type : Manual
Triggered By : User Name (user@company.com)
```

## Recommended Settings

```python
window_minutes=15
retry_count=10
retry_interval_seconds=60
```
