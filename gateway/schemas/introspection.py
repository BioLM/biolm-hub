from pydantic import BaseModel


class IntrospectionUser(BaseModel):
    id: str
    username: str
    company_id: str | None  # Consolidated: company_id replaces institute_id
    environment_id: int | None


class IntrospectionAuthorization(BaseModel):
    can_access_api: bool
    reason: str


class UsageState(BaseModel):
    current: int
    limit: int


class BillingState(BaseModel):
    current: str
    limit: str


class IntrospectionUsageState(BaseModel):
    monthly_api_requests: UsageState
    lifetime_api_requests: UsageState


class IntrospectionBillingState(BaseModel):
    monthly_charges: BillingState
    lifetime_charges: BillingState


class IntrospectionPolicy(BaseModel):
    rate_limit_per_minute: int
    bypass_billing: bool
    payment_past_due_or_canceled: bool


class IntrospectionResponse(BaseModel):
    token_is_valid: bool
    user: IntrospectionUser
    authorization: IntrospectionAuthorization
    usage_state: IntrospectionUsageState
    billing_state: IntrospectionBillingState
    policy: IntrospectionPolicy
    cache_ttl_seconds: int
    allowed_models: list[str]
