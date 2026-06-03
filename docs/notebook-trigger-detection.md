# Notebook Trigger Detection

## Overview

Notebook trigger detection resolves who manually triggered a standalone Microsoft Fabric Notebook run.

Standalone notebooks do not use the Data Pipeline `queryactivityruns` API. Instead, the implementation uses notebook job instance metadata to get the notebook start time.

## Flow

```text
Notebook Job Instance
      │
      ▼
Notebook Start Time
      │
      ▼
Admin Activity Events API
      │
      ▼
StartRunNotebook / RunArtifact Event
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
Operation = StartRunNotebook
or
Operation = RunArtifact

ObjectId = notebook_id
```

The implementation prioritises:

```text
StartRunNotebook first
RunArtifact second
```

## Why a Time-Difference Threshold Is Required

Standalone notebooks can be manually run several times within a short period. The audit log only contains the notebook artifact ID, not a unique notebook job instance ID.

Because of that, an old run of the same notebook can appear in the same search window.

To prevent false matches, the implementation uses:

```python
max_allowed_time_diff_seconds=60
```

This rejects audit events that are too far from the notebook start time.

## Retry Logic

Audit events for notebooks may not be visible immediately through the Admin Activity Events API.

Recommended settings:

```python
window_minutes=15
max_allowed_time_diff_seconds=60
retry_count=10
retry_interval_seconds=60
```

## Example Output

```text
Trigger Type : Manual
Triggered By : User Name (user@company.com)
```
