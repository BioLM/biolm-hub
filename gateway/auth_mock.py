from gateway.schemas.introspection import (
    BillingState,
    IntrospectionAuthorization,
    IntrospectionBillingState,
    IntrospectionPolicy,
    IntrospectionResponse,
    IntrospectionUsageState,
    IntrospectionUser,
    UsageState,
)


def get_mock_introspection_response(token: str) -> IntrospectionResponse:
    if token == "invalid-token":
        return IntrospectionResponse(
            token_is_valid=False,
            user=IntrospectionUser(id="", username="", company_id=None),
            authorization=IntrospectionAuthorization(
                can_access_api=False, reason="invalid_token"
            ),
            usage_state=IntrospectionUsageState(
                monthly_api_requests=UsageState(current=0, limit=0),
                lifetime_api_requests=UsageState(current=0, limit=0),
            ),
            billing_state=IntrospectionBillingState(
                monthly_charges=BillingState(current="0", limit="0"),
                lifetime_charges=BillingState(current="0", limit="0"),
            ),
            policy=IntrospectionPolicy(
                rate_limit_per_minute=0,
                bypass_billing=False,
                payment_past_due_or_canceled=False,
            ),
            cache_ttl_seconds=60,
            allowed_models=[],
        )

    return IntrospectionResponse(
        token_is_valid=True,
        user=IntrospectionUser(
            id="some-user-id",
            username="testuser",
            company_id="some-company-id",
        ),
        authorization=IntrospectionAuthorization(can_access_api=True, reason="ok"),
        usage_state=IntrospectionUsageState(
            monthly_api_requests=UsageState(current=50, limit=10000),
            lifetime_api_requests=UsageState(current=500, limit=100000),
        ),
        billing_state=IntrospectionBillingState(
            monthly_charges=BillingState(current="25.5000", limit="100.0000"),
            lifetime_charges=BillingState(current="250.7500", limit="500.0000"),
        ),
        policy=IntrospectionPolicy(
            rate_limit_per_minute=100,
            bypass_billing=False,
            payment_past_due_or_canceled=False,
        ),
        cache_ttl_seconds=60,
        allowed_models=["esm2-650m-encode", "protein-mpnn-generate"],
    )
