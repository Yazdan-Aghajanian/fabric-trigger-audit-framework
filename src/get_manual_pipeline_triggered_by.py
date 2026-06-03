"""
Resolve who manually triggered a Microsoft Fabric Pipeline.

This function is designed to run inside a Microsoft Fabric Notebook because it uses:
- mssparkutils.credentials.getToken("https://api.fabric.microsoft.com")
- Fabric Data Pipeline activity run APIs

Sensitive values such as tenant ID, client ID and client secret must be provided securely.
Do not hard-code secrets in production notebooks.
"""

import time
import requests
import pandas as pd

try:
    from notebookutils import mssparkutils
except Exception:
    mssparkutils = None


def get_manual_pipeline_triggered_by(
    tenant_id,
    client_id,
    client_secret,
    workspace_id,
    pipeline_id,
    pipeline_run_id,
    window_minutes=15,
    retry_count=10,
    retry_interval_seconds=60
):
    """
    Resolve who manually triggered a Fabric pipeline run.

    Logic:
    1. Use Fabric queryactivityruns API to find the actual pipeline run start time.
    2. Use Power BI Admin Activity Events API to search audit events around that time.
    3. Find Operation = RunArtifact where ObjectId = pipeline_id.
    4. Return the UserId from the closest audit event.

    Note:
    Audit logs do not directly store Fabric pipeline_run_id, so matching is done by:
        Pipeline ID + RunArtifact + closest CreationTime.
    """

    try:
        if mssparkutils is None:
            raise RuntimeError(
                "mssparkutils is not available. This function must run inside Microsoft Fabric."
            )

        # ----------------------------------------------------------
        # Token 1: Fabric API token
        # Used for queryactivityruns
        # ----------------------------------------------------------
        print("\n" + "=" * 100)
        print("STEP 1 - GET FABRIC API TOKEN")
        print("=" * 100)

        fabric_token = mssparkutils.credentials.getToken(
            "https://api.fabric.microsoft.com"
        )

        fabric_headers = {
            "Authorization": f"Bearer {fabric_token}",
            "Content-Type": "application/json"
        }

        print("✅ Fabric token generated successfully")

        # ----------------------------------------------------------
        # Get activity runs for this pipeline run
        # ----------------------------------------------------------
        activity_runs_url = (
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
            f"/datapipelines/pipelineruns/{pipeline_run_id}/queryactivityruns"
        )

        activity_payload = {
            "lastUpdatedAfter": "2026-01-01T00:00:00Z",
            "lastUpdatedBefore": "2026-12-31T23:59:59Z",
            "filters": [],
            "orderBy": [
                {
                    "orderBy": "ActivityRunStart",
                    "order": "ASC"
                }
            ]
        }

        activity_response = requests.post(
            activity_runs_url,
            headers=fabric_headers,
            json=activity_payload
        )

        print("\n" + "=" * 100)
        print("STEP 2 - GET PIPELINE ACTIVITY RUNS")
        print("=" * 100)
        print("Activity Runs HTTP Status:", activity_response.status_code)

        if activity_response.status_code != 200:
            print("Manual trigger lookup failed at Fabric Activity Runs API:")
            print(activity_response.text[:500])
            return None

        activity_rows = activity_response.json().get("value", [])

        print("Activity Rows Returned   :", len(activity_rows))

        if not activity_rows:
            print("Manual trigger lookup: no activity rows returned.")
            return None

        df_activities = pd.json_normalize(activity_rows)

        start_col = None

        for col in ["activityRunStart", "ActivityRunStart", "startTime", "StartTime"]:
            if col in df_activities.columns:
                start_col = col
                break

        if not start_col:
            print("Manual trigger lookup: no activity start time column found.")
            return None

        run_start_utc = pd.to_datetime(
            df_activities[start_col],
            utc=True,
            errors="coerce"
        ).min()

        if pd.isna(run_start_utc):
            print("Manual trigger lookup: could not parse run start time.")
            return None

        run_start_adelaide = run_start_utc.tz_convert("Australia/Adelaide")

        print("\n" + "=" * 100)
        print("STEP 3 - RESOLVE PIPELINE RUN START TIME")
        print("=" * 100)
        print("Pipeline Run ID        :", pipeline_run_id)
        print("Start Column Used      :", start_col)
        print("Pipeline Start UTC     :", run_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
        print("Pipeline Start Adelaide:", run_start_adelaide.strftime("%Y-%m-%d %I:%M:%S %p"))

        # ----------------------------------------------------------
        # Token 2: Power BI Admin Activity Events API token
        # Used for admin/activityevents
        # ----------------------------------------------------------
        print("\n" + "=" * 100)
        print("STEP 4 - GET POWER BI ADMIN API TOKEN")
        print("=" * 100)

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        token_body = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default"
        }

        token_response = requests.post(
            token_url,
            data=token_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        print("Power BI Token HTTP Status:", token_response.status_code)

        if token_response.status_code != 200:
            print("Manual trigger lookup failed at Power BI token generation:")
            print(token_response.text[:500])
            return None

        powerbi_token = token_response.json()["access_token"]

        print("✅ Power BI token generated successfully")

        powerbi_headers = {
            "Authorization": f"Bearer {powerbi_token}",
            "Content-Type": "application/json"
        }

        print("\n" + "=" * 100)
        print("STEP 5 - RETRY ADMIN ACTIVITY EVENTS LOOKUP")
        print("=" * 100)
        print("Retry Count            :", retry_count)
        print("Retry Interval Seconds :", retry_interval_seconds)
        print("Window Minutes         :", window_minutes)

        for retry_attempt in range(1, retry_count + 1):

            print("\n" + "-" * 100)
            print(f"RETRY ATTEMPT {retry_attempt} OF {retry_count}")
            print("-" * 100)

            # ----------------------------------------------------------
            # Build audit search windows
            # Admin Activity Events API cannot cross UTC date boundary,
            # so split into multiple calls if needed.
            # ----------------------------------------------------------
            search_start_dt = run_start_utc - pd.Timedelta(minutes=window_minutes)
            search_end_dt = run_start_utc + pd.Timedelta(minutes=window_minutes)

            search_windows = []

            if search_start_dt.date() == search_end_dt.date():
                search_windows.append((search_start_dt, search_end_dt))
            else:
                end_of_first_day = (
                    search_start_dt.normalize()
                    + pd.Timedelta(days=1)
                    - pd.Timedelta(seconds=1)
                )

                start_of_second_day = search_end_dt.normalize()

                search_windows.append((search_start_dt, end_of_first_day))
                search_windows.append((start_of_second_day, search_end_dt))

            print("\n" + "=" * 100)
            print("STEP 5 - BUILD ADMIN ACTIVITY EVENTS SEARCH WINDOWS")
            print("=" * 100)
            print("Original Search Start UTC:", search_start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
            print("Original Search End UTC  :", search_end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"))

            for i, (window_start, window_end) in enumerate(search_windows, start=1):
                print(
                    f"Search Window #{i}: "
                    f"{window_start.strftime('%Y-%m-%dT%H:%M:%S.000Z')} "
                    f"to "
                    f"{window_end.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
                )

            # ----------------------------------------------------------
            # Get audit events
            # ----------------------------------------------------------
            print("\n" + "=" * 100)
            print("STEP 6 - QUERY ADMIN ACTIVITY EVENTS")
            print("=" * 100)

            events = []

            for i, (window_start, window_end) in enumerate(search_windows, start=1):

                search_start_str = window_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                search_end_str = window_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")

                print(f"\nProcessing Audit Window #{i}")
                print(f"Search Start UTC : {search_start_str}")
                print(f"Search End UTC   : {search_end_str}")

                activity_events_url = (
                    "https://api.powerbi.com/v1.0/myorg/admin/activityevents"
                    f"?startDateTime='{search_start_str}'"
                    f"&endDateTime='{search_end_str}'"
                )

                events_response = requests.get(
                    activity_events_url,
                    headers=powerbi_headers
                )

                print("Audit API HTTP Status:", events_response.status_code)

                if events_response.status_code != 200:
                    print("Manual trigger lookup failed at Admin Activity Events API:")
                    print(events_response.text[:500])
                    continue

                events_data = events_response.json()
                window_events = events_data.get("activityEventEntities", [])

                print("Audit Events Returned:", len(window_events))

                events.extend(window_events)

                continuation_uri = events_data.get("continuationUri")

                while continuation_uri:
                    continuation_response = requests.get(
                        continuation_uri,
                        headers=powerbi_headers
                    )

                    if continuation_response.status_code != 200:
                        print("Manual trigger lookup continuation failed:")
                        print(continuation_response.text[:500])
                        break

                    continuation_data = continuation_response.json()
                    continuation_events = continuation_data.get("activityEventEntities", [])

                    print("Additional Audit Events Returned:", len(continuation_events))

                    events.extend(continuation_events)

                    continuation_uri = continuation_data.get("continuationUri")

            print("\nTotal Audit Events Retrieved:", len(events))

            # ----------------------------------------------------------
            # Match RunArtifact audit events for this pipeline ID
            # ----------------------------------------------------------
            print("\n" + "=" * 100)
            print("STEP 7 - MATCH RUNARTIFACT EVENTS")
            print("=" * 100)

            candidates = []

            for event in events:
                operation = event.get("Operation", "")

                object_id = str(
                    event.get("ObjectId")
                    or event.get("ItemId")
                    or event.get("ArtifactId")
                    or ""
                ).lower()

                if operation == "RunArtifact" and object_id == pipeline_id.lower():

                    event_creation_dt = pd.to_datetime(
                        event.get("CreationTime"),
                        utc=True,
                        errors="coerce"
                    )

                    if pd.notna(event_creation_dt):
                        event["_time_diff_seconds"] = abs(
                            (event_creation_dt - run_start_utc).total_seconds()
                        )

                        candidates.append(event)

            print("Pipeline ID                 :", pipeline_id)
            print("Candidate RunArtifact Events:", len(candidates))

            if candidates:
                best_event = sorted(
                    candidates,
                    key=lambda x: x["_time_diff_seconds"]
                )[0]

                triggered_by = best_event.get("UserId")

                print("\n" + "=" * 100)
                print("STEP 8 - RESOLVE TRIGGERING USER")
                print("=" * 100)
                print("Triggered By   :", triggered_by)
                print("Audit Time     :", best_event.get("CreationTime"))
                print("Time Difference:", round(best_event.get("_time_diff_seconds"), 2), "seconds")
                print("Resolved On Retry Attempt:", retry_attempt)

                print("\n" + "=" * 100)
                print("TRIGGER USER RESOLUTION COMPLETED")
                print("=" * 100)

                return triggered_by

            print("\nNo matching pipeline audit event found in this retry.")

            if retry_attempt < retry_count:
                print(f"Waiting {retry_interval_seconds} seconds before next retry...")
                time.sleep(retry_interval_seconds)

        print("\n" + "=" * 100)
        print("PIPELINE TRIGGER USER RESOLUTION FAILED AFTER RETRIES")
        print("=" * 100)
        print("Retry Count Reached :", retry_count)
        print("=" * 100)

        return None

    except Exception as e:
        print("Manual trigger lookup failed with exception:", str(e))
        return None
