from uuid import UUID

from pydantic import BaseModel


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str


class TenantOut(BaseModel):
    id: UUID
    slug: str
    name: str


class TenantMembershipOut(TenantOut):
    role: str


class MeOut(BaseModel):
    user: UserOut
    tenant: TenantOut
    role: str
    permissions: list[str]
    tenants: list[TenantMembershipOut]
