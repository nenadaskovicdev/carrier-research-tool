from config import API_SEARCH


def search_worker_detailed(session, search_data):
    """
    search_data should be a dict with keys:
    - EmployerName
    - City
    - State
    - CoverageDate
    - Fein (optional)
    - StreetAddress (optional)
    - ZipCode (optional)
    """
    params = {"handler": "PolicyHolderDetails", **search_data}

    # Remove empty parameters
    params = {k: v for k, v in params.items() if v}

    print(f"Searching with params: {params}")

    r = session.get(API_SEARCH, params=params)

    print(f"Search Status Code: {r.status_code}")
    print(f"Search Response Headers: {dict(r.headers)}")

    r.raise_for_status()

    # Try to parse as JSON, if fails return text
    try:
        return r.json()
    except:
        return r.text
