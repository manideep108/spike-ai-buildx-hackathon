"""
GA4 metrics and dimensions allowlists.
Used to validate LLM-generated queries and prevent injection attacks.
"""

# Valid GA4 Metrics
# Reference: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
VALID_METRICS = {
    # User metrics
    "activeUsers",
    "newUsers",
    "totalUsers",
    
    # Session metrics
    "sessions",
    "sessionsPerUser",
    "averageSessionDuration",
    "engagementRate",
    "bounceRate",
    
    # Page/Screen metrics
    "screenPageViews",
    "screenPageViewsPerSession",
    
    # Event metrics
    "eventCount",
    "eventsPerSession",
    "conversions",
    
    # Engagement metrics
    "engagedSessions",
    "userEngagementDuration",
    
    # E-commerce metrics
    "totalRevenue",
    "purchaseRevenue",
    "transactions",
    "addToCarts",
    
    # Alternative names for common metrics
    "users",  # alias for totalUsers
    "pageviews",  # alias for screenPageViews
    "pageViews",
}

# Valid GA4 Dimensions
VALID_DIMENSIONS = {
    # Time dimensions
    "date",
    "year",
    "month",
    "week",
    "day",
    "hour",
    "yearMonth",
    "yearWeek",
    
    # Geography dimensions
    "country",
    "city",
    "region",
    "continent",
    
    # Technology dimensions
    "browser",
    "deviceCategory",
    "operatingSystem",
    "platform",
    "mobileDeviceBranding",
    "mobileDeviceModel",
    
    # Page/Screen dimensions
    "pagePath",
    "pageTitle",
    "landingPage",
    "hostName",
    "unifiedScreenName",
    
    # Traffic source dimensions
    "source",
    "medium",
    "campaign",
    "campaignName",
    "sessionSource",
    "sessionMedium",
    "sessionCampaignName",
    "firstUserSource",
    "firstUserMedium",
    
    # User dimensions
    "newVsReturning",
    "userAgeBracket",
    "userGender",
    "language",
    
    # Event dimensions
    "eventName",
    
    # Alternative names
    "pageURL",  # Similar to pagePath
}


def is_valid_metric(metric: str) -> bool:
    """Check if a metric is in the allowlist."""
    return metric in VALID_METRICS


def is_valid_dimension(dimension: str) -> bool:
    """Check if a dimension is in the allowlist."""
    return dimension in VALID_DIMENSIONS


def validate_metrics(metrics: list[str]) -> tuple[bool, list[str]]:
    """
    Validate a list of metrics.
    
    Returns:
        (is_valid, invalid_metrics)
    """
    invalid = [m for m in metrics if not is_valid_metric(m)]
    return len(invalid) == 0, invalid


def validate_dimensions(dimensions: list[str]) -> tuple[bool, list[str]]:
    """
    Validate a list of dimensions.
    
    Returns:
        (is_valid, invalid_dimensions)
    """
    invalid = [d for d in dimensions if not is_valid_dimension(d)]
    return len(invalid) == 0, invalid
