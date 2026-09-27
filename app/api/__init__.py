from app.api.auth import router as auth_router
from app.api.employees import router as employees_router
from app.api.contracts import router as contracts_router
from app.api.system import router as system_router

__all__ = ["auth_router", "employees_router", "contracts_router", "system_router"]
