# Audit Log Delay Analysis

## Key Finding

During testing, audit events were generated close to the actual notebook or pipeline start time, but they were not always visible immediately through the Admin Activity Events API.

This is best described as:

```text
Audit API visibility delay
```

or:

```text
Audit log ingestion delay
```

## Example

```text
Notebook Start Time : 05:21:41 UTC
Audit Event Time    : 05:21:51 UTC
```

The event timestamp was only around 10 seconds after the notebook start time.

However, the event was not returned by the Admin Activity Events API until several minutes later.

## Interpretation

This suggests:

```text
The audit event is created quickly.
The Admin Activity Events API exposes it after internal processing/indexing delay.
```

## Why Retry Logic Is Needed

A single API call during the same running notebook or pipeline may return no matching audit event.

The retry loop allows the function to wait until the event becomes visible.

Recommended retry settings:

```python
retry_count=10
retry_interval_seconds=60
```

This checks once per minute for up to 10 minutes.

## Why Notebook Matching Also Uses a Rejection Threshold

Notebook runs are more ambiguous than pipeline runs because the audit event does not contain a unique notebook job instance ID.

If the same notebook is manually executed multiple times, old runs can appear in the search window.

To avoid using an old audit event, the notebook function rejects matches where the audit event time is too far from the notebook start time.

Recommended threshold:

```python
max_allowed_time_diff_seconds=60
```
