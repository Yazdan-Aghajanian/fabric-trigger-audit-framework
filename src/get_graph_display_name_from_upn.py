"""
Resolve a Microsoft Entra user display name from a UPN/email address using Microsoft Graph.

Required Microsoft Graph application permission:
- User.Read.All
- Admin consent granted
"""

import requests


def get_graph_display_name_from_upn(
    tenant_id,
    client_id,
    client_secret,
    upn,
    verbose=True
):
    """
    Resolve display name from Microsoft Graph using UPN/email.

    Input:
        user@company.com

    Output:
        User Name (user@company.com)

    Uses service principal token instead of mssparkutils Graph token,
    because mssparkutils.credentials.getToken("https://graph.microsoft.com/")
    can fail inside Fabric runtime.
    """

    if not upn:
        if verbose:
            print("\n" + "=" * 100)
            print("GRAPH USER RESOLUTION SKIPPED")
            print("=" * 100)
            print("Reason: Empty UPN provided")
            print("=" * 100)
        return "Unknown"

    try:
        # ----------------------------------------------------------
        # Get Microsoft Graph token using service principal
        # ----------------------------------------------------------
        if verbose:
            print("\n" + "=" * 100)
            print("STEP 1 - GET MICROSOFT GRAPH TOKEN")
            print("=" * 100)

        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        token_body = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }

        token_response = requests.post(
            token_url,
            data=token_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )

        if verbose:
            print("Graph Token HTTP Status:", token_response.status_code)

        if token_response.status_code != 200:
            if verbose:
                print("Graph token generation failed:")
                print(token_response.text[:500])
                print("=" * 100)
            return upn

        graph_token = token_response.json()["access_token"]

        if verbose:
            print("✅ Microsoft Graph token generated successfully")

        graph_headers = {
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json"
        }

        # ----------------------------------------------------------
        # Get user by UPN/email
        # ----------------------------------------------------------
        if verbose:
            print("\n" + "=" * 100)
            print("STEP 2 - LOOKUP USER IN MICROSOFT GRAPH")
            print("=" * 100)
            print("Input UPN:", upn)

        graph_url = (
            f"https://graph.microsoft.com/v1.0/users/{upn}"
            "?$select=displayName,userPrincipalName"
        )

        graph_response = requests.get(
            graph_url,
            headers=graph_headers,
            timeout=30
        )

        if verbose:
            print("Graph User Lookup HTTP Status:", graph_response.status_code)

        if graph_response.status_code != 200:
            if verbose:
                print("Graph user lookup failed:")
                print(graph_response.text[:500])
                print("=" * 100)
            return upn

        user = graph_response.json()

        display_name = user.get("displayName")
        user_principal_name = user.get("userPrincipalName") or upn

        if verbose:
            print("\n" + "=" * 100)
            print("STEP 3 - RESOLVE DISPLAY NAME")
            print("=" * 100)
            print("Display Name :", display_name)
            print("UPN          :", user_principal_name)

        if display_name:

            resolved_name = f"{display_name} ({user_principal_name})"

            if verbose:
                print("\n" + "=" * 100)
                print("GRAPH USER RESOLUTION COMPLETED")
                print("=" * 100)
                print("Resolved User:", resolved_name)
                print("=" * 100)

            return resolved_name

        if verbose:
            print("\n" + "=" * 100)
            print("GRAPH USER RESOLUTION COMPLETED")
            print("=" * 100)
            print("Resolved User:", user_principal_name)
            print("=" * 100)

        return user_principal_name

    except Exception as e:
        if verbose:
            print("\n" + "=" * 100)
            print("GRAPH USER RESOLUTION FAILED")
            print("=" * 100)
            print("Error:", str(e))
            print("Fallback User:", upn)
            print("=" * 100)

        return upn
