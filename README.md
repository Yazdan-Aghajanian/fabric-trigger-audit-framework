# Fabric Trigger Audit Framework

Microsoft Fabric framework for identifying who manually triggered Pipelines and standalone Notebooks using Fabric APIs, Power BI / Fabric Admin Activity Events API, Microsoft Graph API, and retry handling for audit-log visibility delays.

## What It Solves

This framework answers a common operational question:

```text
Who manually triggered this Fabric Pipeline or Notebook?
```

It supports:

- Microsoft Fabric Pipelines
- Standalone Microsoft Fabric Notebooks
- Trigger user identification from Admin Activity Events
- Display name resolution from email/UPN using Microsoft Graph
- Audit log visibility delay handling through configurable retry logic
- Safe fallback behaviour when no valid audit event is found
- Logging and reporting integration

---

## Overview

Fabric Trigger Audit Framework is a Microsoft Fabric auditing solution that identifies who manually triggered:

- Microsoft Fabric Pipelines
- Standalone Microsoft Fabric Notebooks

The framework combines:

- Fabric REST APIs
- Power BI / Fabric Admin Activity Events API
- Microsoft Graph API

to resolve the actual user who initiated a run and record the information in logs, audit tables, and reporting layers.

---

## Problem Statement

Microsoft Fabric provides execution context for pipelines and notebooks, but determining the actual user who initiated a manual run can be challenging.

Typical runtime metadata often provides:

- Current execution identity
- Service principal identity
- Notebook runtime context

However, operational teams frequently need answers to questions such as:

- Who manually started this pipeline?
- Who manually executed this notebook?
- Was this run scheduled or manually triggered?
- Which user initiated the execution?

---

## Solution

The framework correlates execution metadata with Microsoft Fabric audit logs.

### Pipeline Flow

```text
Pipeline Run
      │
      ▼
Query Activity Runs API
      │
      ▼
Resolve Actual Run Start Time
      │
      ▼
Admin Activity Events API
      │
      ▼
Match RunArtifact Event
      │
      ▼
Extract UserId (UPN)
      │
      ▼
Microsoft Graph API
      │
      ▼
Display Name Resolution
```

### Notebook Flow

```text
Notebook Run
      │
      ▼
Job Instance Metadata
      │
      ▼
Resolve Notebook Start Time
      │
      ▼
Admin Activity Events API
      │
      ▼
Match StartRunNotebook / RunArtifact Event
      │
      ▼
Extract UserId (UPN)
      │
      ▼
Microsoft Graph API
      │
      ▼
Display Name Resolution
```

---

## Key Features

- Detect manual Fabric Pipeline executions
- Detect manual standalone Fabric Notebook executions
- Resolve triggering user from Admin Activity Events API
- Convert UPN/email to display name using Microsoft Graph
- Handle audit log visibility delays using configurable retry logic
- Store audit information in logs and reporting layers
- Production-ready implementation for Fabric environments

---

## Audit Log Visibility Delay

One key discovery during implementation was that audit events are often not immediately visible through the Admin Activity Events API.

Example:

```text
Notebook Start Time : 05:21:41
Audit Event Time    : 05:21:51
```

Although the event was generated almost immediately, it did not become available through the API until several minutes later.

To address this, the framework includes configurable retry logic.

```python
retry_count=10
retry_interval_seconds=60
```

This allows the framework to wait for the audit event to become available before resolving the triggering user.

---

## Example Output

### Manual Pipeline Run

```text
Trigger Type : Manual
Triggered By : User Name (user@company.com)
```

### Manual Notebook Run

```text
Trigger Type : Manual
Triggered By : User Name (user@company.com)
```

### Scheduled Run

```text
Trigger Type : Scheduled
Triggered By : Scheduling Module
```

### Orchestrator Pipeline Run

```text
Trigger Type : Orchestrator Pipeline
Triggered By : Parent_Pipeline_Name
```

---

## Logging Integration

The framework can write the resolved trigger information into:

- Text execution logs
- Audit tables
- Operational monitoring tables
- Daily Fabric Run Summary reports

Example columns:

| Column |
|----------|
| Trigger Type |
| Triggered By |
| Trigger Time |
| Trigger Source |

---

## Microsoft Graph Integration

The audit logs typically return:

```text
user@company.com
```

Microsoft Graph is then used to resolve:

```text
User Name (user@company.com)
```

using:

```http
GET /users/{userPrincipalName}
```

---

## Required Permissions

### Fabric

- Workspace access
- Activity Runs API access

### Power BI / Fabric

- Fabric Administrator or equivalent access
- Admin Activity Events API access

### Microsoft Graph

Application permission:

```text
User.Read.All
```

with admin consent.

---

## Repository Structure

```text
fabric-trigger-audit-framework
│
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
│
├── docs
│   ├── architecture.md
│   ├── notebook-trigger-detection.md
│   ├── pipeline-trigger-detection.md
│   └── audit-log-delay-analysis.md
│
├── src
│   ├── get_manual_pipeline_triggered_by.py
│   ├── get_manual_notebook_triggered_by.py
│   ├── get_graph_display_name_from_upn.py
│   └── query_admin_activity_events.py
│
└── examples
    ├── pipeline_example.py
    └── notebook_example.py
```

---

## Security

Never commit:

- Client secrets
- Access tokens
- Tenant-specific credentials
- Production endpoints
- Workspace IDs
- Pipeline IDs
- Notebook IDs
- Real user names or email addresses

Use:

```text
.env.example
```

for configuration templates only.

Store secrets securely using:

- Azure Key Vault
- Environment Variables
- Fabric Credential Management

Never hard-code secrets into notebooks or source files.

---

## Future Enhancements

- Native Fabric Monitoring integration
- Centralised audit dashboard
- Trigger analytics reporting
- Historical trigger trend analysis
- Multi-tenant support

---

## License

MIT License

---

## Contributions

Contributions, feedback, and improvement suggestions are welcome.

If this repository helps you solve a similar auditing challenge in Microsoft Fabric, feel free to open an issue or submit a pull request.
