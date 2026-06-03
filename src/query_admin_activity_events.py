"""
Query Power BI / Fabric Admin Activity Events API.

This helper:
- Accepts a Power BI Admin API authorization header.
- Splits the search window if it crosses a UTC date boundary.
- Handles continuationUri pagination.
- Returns all audit event entities.
"""

import requests
import pandas as pd


def query_admin_activity_events(
    powerbi_headers,
    search_start_dt,
    search_end_dt,
    verbose=True
):
    """
    Query Power BI / Fabric Admin Activity Events API.

    Parameters
    ----------
    powerbi_headers : dict
        Authorization headers containing a valid Power BI Admin API bearer token.

    search_start_dt : pandas.Timestamp
        UTC search start datetime.

    search_end_dt : pandas.Timestamp
        UTC search end datetime.

    verbose : bool
        If True, prints diagnostic output.

    Returns
    -------
    list[dict]
        List of Admin Activity Events API entities.
    """

    search_start_dt = pd.to_datetime(search_start_dt, utc=True)
    search_end_dt = pd.to_datetime(search_end_dt, utc=True)

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

    if verbose:
        print("\n" + "=" * 100)
        print("BUILD ADMIN ACTIVITY EVENTS SEARCH WINDOWS")
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

        print("\n" + "=" * 100)
        print("QUERY ADMIN ACTIVITY EVENTS")
        print("=" * 100)

    events = []

    for i, (window_start, window_end) in enumerate(search_windows, start=1):

        search_start_str = window_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        search_end_str = window_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        if verbose:
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

        if verbose:
            print("Audit API HTTP Status:", events_response.status_code)

        if events_response.status_code != 200:
            if verbose:
                print("Admin Activity Events API failed:")
                print(events_response.text[:500])
            events_response.raise_for_status()

        events_data = events_response.json()
        window_events = events_data.get("activityEventEntities", [])

        if verbose:
            print("Audit Events Returned:", len(window_events))

        events.extend(window_events)

        continuation_uri = events_data.get("continuationUri")

        while continuation_uri:
            continuation_response = requests.get(
                continuation_uri,
                headers=powerbi_headers
            )

            if verbose:
                print("Continuation HTTP Status:", continuation_response.status_code)

            if continuation_response.status_code != 200:
                if verbose:
                    print("Admin Activity Events API continuation failed:")
                    print(continuation_response.text[:500])
                continuation_response.raise_for_status()

            continuation_data = continuation_response.json()
            continuation_events = continuation_data.get("activityEventEntities", [])

            if verbose:
                print("Additional Audit Events Returned:", len(continuation_events))

            events.extend(continuation_events)

            continuation_uri = continuation_data.get("continuationUri")

    if verbose:
        print("\nTotal Audit Events Retrieved:", len(events))

    return events
