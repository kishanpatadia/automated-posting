"""FastAPI app and routes."""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.platforms import REGISTRY
from app.schemas import ErrorResponse, PostingRequest, PostingResponse, ValidationErrorItem
from app.services.posting_service import PostingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Automated Multi-Platform Posting",
    version="1.0.0",
    description=(
        "Publishes a short message with one call-to-action link to several third-party platforms "
        f"({', '.join(cls.name for cls in REGISTRY.values())}). Each platform is handled independently: "
        "one failure never stops the others."
    ),
)


def get_posting_service() -> PostingService:
    return PostingService(get_settings())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        location = [str(part) for part in err.get("loc", ()) if part != "body"]
        message = err.get("msg", "Invalid value").removeprefix("Value error, ")
        if err.get("type") == "missing":
            message = "This field is required."
        elif err.get("type") == "json_invalid":
            message = "Request body is not valid JSON."
        errors.append(ValidationErrorItem(field=".".join(location) or "body", error=message))
    return JSONResponse(status_code=422, content=ErrorResponse(errors=errors).model_dump())


@app.post(
    "/posting",
    response_model=PostingResponse,
    responses={422: {"model": ErrorResponse, "description": "Invalid message"}},
    summary="Publish a message to all enabled platforms",
)
async def create_posting(
    payload: PostingRequest, service: PostingService = Depends(get_posting_service)
) -> PostingResponse:
    results = await service.post(payload.message, payload.cta_url)
    return PostingResponse(success=any(r.status == "success" for r in results), results=results)


@app.get("/platforms", summary="List platforms and whether each one is configured")
async def list_platforms(service: PostingService = Depends(get_posting_service)) -> list[dict]:
    return [
        {"platform": p.name, "configured": not p.missing_settings(), "missing": p.missing_settings()}
        for p in service.platforms
    ]


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"status": "ok"}
