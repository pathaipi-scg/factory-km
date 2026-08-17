"""Engineering extraction review APIs; command execution is intentionally absent."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.config.mssql import MSSQLSettings
from backend.db.mssql import MSSQLConnectionFactory
from backend.domain.engineering_review import EngineeringReviewConcurrencyError, EngineeringReviewError
from backend.repositories.engineering_review_mssql import EngineeringMSSQLDatabase, MSSQLEngineeringReviewRepository
from backend.services.engineering_review_service import EngineeringReviewNotFoundError, EngineeringReviewService
from backend.routers.upload import get_training_gateway_role, _write_allowed


router=APIRouter(prefix="/engineering")


def get_engineering_review_service(request:Request)->EngineeringReviewService:
    configured=getattr(request.app.state,"engineering_review_service",None)
    if isinstance(configured,EngineeringReviewService):return configured
    database=EngineeringMSSQLDatabase(MSSQLConnectionFactory(MSSQLSettings.from_environment()))
    return EngineeringReviewService(MSSQLEngineeringReviewRepository(database))


def review_json(review,run=None,commands=()):
    value=asdict(review); value["status"]=review.status.value; value["concurrency_token"]=review.concurrency_token.hex()
    value["decisions"]=[{**asdict(x),"kind":x.kind.value,"action":x.action.value} for x in review.decisions]
    if run is not None:value["extraction"]={"extraction_run_id":run.extraction_run_id,"source_document_id":run.source_document_id,"source_resource_id":run.source_resource_id,"document_type":run.document_type,"snapshot":run.snapshot}
    value["commands"]=[{**asdict(x),"status":x.status.value,"payload":x.payload} for x in commands]
    return value


def token(value:Any)->bytes:
    try:return bytes.fromhex(str(value))
    except ValueError as error:raise EngineeringReviewError("Concurrency token is invalid.") from error


def api_error(error:Exception):
    status=409 if isinstance(error,EngineeringReviewConcurrencyError) else 404 if isinstance(error,EngineeringReviewNotFoundError) else 400
    return JSONResponse(status_code=status,content={"success":False,"error":str(error)})


@router.post("/extractions/{extraction_run_id}/reviews")
async def create_review(extraction_run_id:str,request:Request,role:str=Depends(get_training_gateway_role)):
    if denied:=_write_allowed(role):return denied
    try:
        payload=await request.json(); review=get_engineering_review_service(request).create_review(extraction_run_id,payload.get("actor_id") if isinstance(payload,dict) else None)
        return {"success":True,"review":review_json(review)}
    except (EngineeringReviewError,EngineeringReviewNotFoundError,ValueError) as error:return api_error(error)


@router.get("/reviews/{review_id}")
def get_review(review_id:str,request:Request):
    try:
        service=get_engineering_review_service(request); review,run=service.get(review_id)
        return {"success":True,"review":review_json(review,run,service.repository.list_commands(review_id))}
    except (EngineeringReviewError,EngineeringReviewNotFoundError,ValueError) as error:return api_error(error)


@router.put("/reviews/{review_id}")
async def update_review(review_id:str,request:Request,role:str=Depends(get_training_gateway_role)):
    if denied:=_write_allowed(role):return denied
    try:
        payload=await request.json(); review=get_engineering_review_service(request).update(review_id,payload.get("decisions",[]),payload.get("intended_kepware_paths",[]),token(payload.get("concurrency_token")))
        return {"success":True,"review":review_json(review)}
    except (EngineeringReviewError,EngineeringReviewNotFoundError,EngineeringReviewConcurrencyError,ValueError) as error:return api_error(error)


@router.post("/reviews/{review_id}/confirm")
async def confirm_review(review_id:str,request:Request,role:str=Depends(get_training_gateway_role)):
    if denied:=_write_allowed(role):return denied
    try:
        payload=await request.json(); review,commands=get_engineering_review_service(request).confirm(review_id,token(payload.get("concurrency_token")))
        return {"success":True,"review":review_json(review,commands=commands),"notice":"READY commands were not executed against OpcTagManager."}
    except (EngineeringReviewError,EngineeringReviewNotFoundError,EngineeringReviewConcurrencyError,ValueError) as error:return api_error(error)


@router.post("/reviews/{review_id}/cancel")
async def cancel_review(review_id:str,request:Request,role:str=Depends(get_training_gateway_role)):
    if denied:=_write_allowed(role):return denied
    try:
        payload=await request.json(); review=get_engineering_review_service(request).cancel(review_id,token(payload.get("concurrency_token")))
        return {"success":True,"review":review_json(review)}
    except (EngineeringReviewError,EngineeringReviewNotFoundError,EngineeringReviewConcurrencyError,ValueError) as error:return api_error(error)


@router.get("/reviews/{review_id}/commands")
def get_commands(review_id:str,request:Request):
    try:
        service=get_engineering_review_service(request); service.get(review_id)
        return {"success":True,"commands":review_json(service.repository.get_review(review_id),commands=service.repository.list_commands(review_id))["commands"],"execution_available":False}
    except (EngineeringReviewError,EngineeringReviewNotFoundError,ValueError) as error:return api_error(error)
