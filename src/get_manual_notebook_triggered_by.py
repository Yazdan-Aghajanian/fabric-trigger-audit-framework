"""
Resolve who manually triggered a standalone Microsoft Fabric Notebook.

This function is designed to run inside a Microsoft Fabric Notebook.

Important:
- Standalone Notebook audit events may not be visible immediately through the Admin Activity Events API.
- Retry logic is required for reliable same-run detection.
- max_allowed_time_diff_seconds prevents accidentally matching older runs of the same notebook.
"""

import time
import requests
import pandas as pd


def get_manual_notebook_triggered_by(
    tenant_id,
    client_id,
    client_secret,
    workspace_id,
    notebook_id,
    notebook_start_time_utc,
    window_minutes=15,
    max_allowed_time_diff_seconds=60,
    retry_count=10,
    retry_interval_seconds=60
):
    """
    Resolve who manually triggered a standalone Fabric notebook run.

    Logic:
    1. Use the notebook job start time already returned from the notebook job instance details.
    2. Use Power BI Admin Activity Events API to search audit events around that time.
    3. Retry the audit lookup until a valid matching audit event appears or retry limit is reached.
    4. Find notebook run audit events where:
        Operation = StartRunNotebook or RunArtifact
        ObjectId  = notebook_id
    5. Prefer StartRunNotebook over RunArtifact.
    6. Return the UserId from the closest valid audit event.

    Note:
    Standalone notebook runs do not use the Data Pipeline queryactivityruns API.
    Matching is done by:
        Notebook ID + notebook run operation + closest CreationTime.
    """

    try:
        # ----------------------------------------------------------
        # Resolve notebook run start time
        # ----------------------------------------------------------
        run_start_utc = pd.to_datetime(
            notebook_start_time_utc,
            utc=True,
            errors="coerce"
        )

        if pd.isna(run_start_utc):
            print("Manual notebook trigger lookup: could not parse notebook start time.")
            return None

        run_start_adelaide = run_start_utc.tz_convert("Australia/Adelaide")

        print("\n" + "=" * 100)
        print("STEP 1 - RESOLVE NOTEBOOK RUN START TIME")
        print("=" * 100)
        print("Notebook ID            :", notebook_id)
        print("Notebook Start UTC     :", run_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
        print("Notebook Start Adelaide:", run_start_adelaide.strftime("%Y-%m-%d %I:%M:%S %p"))

        # ----------------------------------------------------------
        # Token: Power BI Admin Activity Events API token
        # Used for admin/activityevents
        # ----------------------------------------------------------
        print("\n" + "=" * 100)
        print("STEP 2 - GET POWER BI ADMIN API TOKEN")
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
            print("Manual notebook trigger lookup failed at Power BI token generation:")
            print(token_response.text[:500])
            return None

        powerbi_token = token_response.json()["access_token"]

        print("✅ Power BI token generated successfully")

        powerbi_headers = {
            "Authorization": f"Bearer {powerbi_token}",
            "Content-Type": "application/json"
        }

        print("\n" + "=" * 100)
        print("STEP 3 - RETRY ADMIN ACTIVITY EVENTS LOOKUP")
        print("=" * 100)
        print("Retry Count              :", retry_count)
        print("Retry Interval Seconds   :", retry_interval_seconds)
        print("Window Minutes           :", window_minutes)
        print("Allowed Time Difference  :", max_allowed_time_diff_seconds, "seconds")

        latest_rejected_event = None

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
                    print("Manual notebook trigger lookup failed at Admin Activity Events API:")
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
                        print("Manual notebook trigger lookup continuation failed:")
                        print(continuation_response.text[:500])
                        break

                    continuation_data = continuation_response.json()
                    continuation_events = continuation_data.get("activityEventEntities", [])

                    print("Additional Audit Events Returned:", len(continuation_events))

                    events.extend(continuation_events)

                    continuation_uri = continuation_data.get("continuationUri")

            print("\nTotal Audit Events Retrieved:", len(events))

            # ----------------------------------------------------------
            # Match notebook run audit events for this notebook ID
            # ----------------------------------------------------------
            print("\n" + "=" * 100)
            print("MATCH NOTEBOOK RUN EVENTS")
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

                if (
                    operation in ["StartRunNotebook", "RunArtifact"]
                    and object_id == notebook_id.lower()
                ):

                    event_creation_dt = pd.to_datetime(
                        event.get("CreationTime"),
                        utc=True,
                        errors="coerce"
                    )

                    if pd.notna(event_creation_dt):
                        event["_time_diff_seconds"] = abs(
                            (event_creation_dt - run_start_utc).total_seconds()
                        )

                        event["_operation_priority"] = {
                            "StartRunNotebook": 1,
                            "RunArtifact": 2
                        }.get(operation, 99)

                        candidates.append(event)

            print("Notebook ID                  :", notebook_id)
            print("Candidate Notebook Run Events:", len(candidates))

            if candidates:
                best_event = sorted(
                    candidates,
                    key=lambda x: (
                        x["_operation_priority"],
                        x["_time_diff_seconds"]
                    )
                )[0]

                latest_rejected_event = best_event

                print("Best Candidate Operation     :", best_event.get("Operation"))
                print("Best Candidate User          :", best_event.get("UserId"))
                print("Best Candidate Audit Time    :", best_event.get("CreationTime"))
                print("Best Candidate Time Diff     :", round(best_event["_time_diff_seconds"], 2), "seconds")

                if best_event["_time_diff_seconds"] <= max_allowed_time_diff_seconds:
                    triggered_by = best_event.get("UserId")

                    print("\n" + "=" * 100)
                    print("NOTEBOOK TRIGGER USER RESOLUTION COMPLETED")
                    print("=" * 100)
                    print("Triggered By   :", triggered_by)
                    print("Audit Time     :", best_event.get("CreationTime"))
                    print("Operation      :", best_event.get("Operation"))
                    print("Time Difference:", round(best_event.get("_time_diff_seconds"), 2), "seconds")
                    print("Resolved On Retry Attempt:", retry_attempt)
                    print("=" * 100)

                    return triggered_by

                print("\nMatch rejected because the closest event is too far from notebook start time.")
                print("Allowed Maximum:", max_allowed_time_diff_seconds, "seconds")

            else:
                print("No matching notebook run audit event found in this retry.")

            if retry_attempt < retry_count:
                print(f"Waiting {retry_interval_seconds} seconds before next retry...")
                time.sleep(retry_interval_seconds)

        print("\n" + "=" * 100)
        print("NOTEBOOK TRIGGER USER RESOLUTION FAILED AFTER RETRIES")
        print("=" * 100)

        if latest_rejected_event:
            print("Last Rejected Audit Time :", latest_rejected_event.get("CreationTime"))
            print("Last Rejected Operation  :", latest_rejected_event.get("Operation"))
            print("Last Rejected User       :", latest_rejected_event.get("UserId"))
            print("Last Rejected Time Diff  :", round(latest_rejected_event["_time_diff_seconds"], 2), "seconds")

        print("Retry Count Reached      :", retry_count)
        print("=" * 100)

        return None

    except Exception as e:
        print("Manual notebook trigger lookup failed with exception:", str(e))
        return None
