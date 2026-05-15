"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import chat, medical_codes, analytics

try:
    from src.agents.devops.interfaces.api import router as devops_router
except Exception as _devops_import_err:  # noqa: BLE001
    devops_router = None
    import logging
    logging.getLogger(__name__).info(
        "DevOps router not loaded: %s", _devops_import_err
    )

app = FastAPI(
    title="HealthFlow RCM System",
    description="Healthcare Revenue Cycle Management with AI Agents",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(medical_codes.router, prefix="/api/v1/medical-codes", tags=["medical-codes"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])

if devops_router is not None:
    app.include_router(devops_router)


@app.get("/")
async def root():
    return {
        "message": "HealthFlow RCM System API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

