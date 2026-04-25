def public_api_only_preprocessing_hook(endpoints):
    allowed_prefixes = ("/api/",)
    excluded_paths = {"/api/schema/"}

    return [
        endpoint
        for endpoint in endpoints
        if endpoint[0].startswith(allowed_prefixes) and endpoint[0] not in excluded_paths
    ]
