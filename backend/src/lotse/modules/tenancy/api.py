"""Thin router: parse, call the service, map the result."""

from typing import Annotated

from fastapi import APIRouter, Depends

from lotse.core.auth import Principal, get_principal
from lotse.core.db import PlatformDB, get_platform_db
from lotse.modules.tenancy import service
from lotse.modules.tenancy.schemas import MeOut

router = APIRouter(tags=["tenancy"])


@router.get("/me", response_model=MeOut)
async def me(
    principal: Annotated[Principal, Depends(get_principal)],
    platform: Annotated[PlatformDB, Depends(get_platform_db)],
) -> MeOut:
    """Current user, the tenant named by X-Tenant, role, permissions, and all memberships."""
    return await service.get_me(platform, principal)
