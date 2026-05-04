import os
import json
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Query, Security, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from .db import db
from .sse import sse_manager

ENV = os.getenv("ENV", "dev")
API_KEY = os.getenv("API_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
security = HTTPBearer()

# Dependency function for database access (enables testing with overrides)


def get_db():
    return db


class RegisterRequest(BaseModel):
    id: str


class EncryptedRecipientKey(BaseModel):
    installation_id: str
    encrypted_key: str


class EncryptedSyncPackage(BaseModel):
    sender_id: str
    iv: str
    ciphertext: str
    recipient_keys: List[EncryptedRecipientKey]


class SyncPushRequest(BaseModel):
    package: EncryptedSyncPackage


class SyncAckRequest(BaseModel):
    package_ids: List[str]
    installation_id: str


class SyncInitRequest(BaseModel):
    uuid: str
    payload: str


class SyncInitDelRequest(BaseModel):
    ids: List[int]
    uuid: str


async def verify_token(
    auth: HTTPAuthorizationCredentials = Security(security), database=Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY is not configured")

    try:
        token = auth.credentials
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        jwt_from_payload = payload.get("jwt")
        if jwt_from_payload is None:
            raise credentials_exception

        # Look up the installation by the FULL JWT token string, not the UUID in the payload
        installation = database.get_installation_by_jwt(token)
        if installation is None:
            raise credentials_exception

        database.touch_installation(token)
        return jwt_from_payload
    except jwt.PyJWTError:
        raise credentials_exception


app = FastAPI(title="Exchange API",
              docs_url="/docs" if ENV == "dev" else None,
              redoc_url="/redoc" if ENV == "dev" else None,
              openapi_url="/openapi.json" if ENV == "dev" else None,
              )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/register")
async def register(
    request: RegisterRequest,
    uuid_to_increment: Optional[str] = Query(None, alias="uuid"),
    database=Depends(get_db),
):
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY is not configured")

    new_installation_uuid = request.id

    # Generate new JWT
    expire = datetime.now(timezone.utc) + timedelta(days=365)
    to_encode = {
        "jwt": str(uuid.uuid4()),
        "issued": datetime.now(timezone.utc).isoformat(),
        "exp": expire.timestamp(),
    }
    new_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")

    initial_installations_count = 1
    if uuid_to_increment:
        existing_installation_data = database.get_installation_by_uuid(uuid_to_increment)
        if existing_installation_data:
            initial_installations_count = (
                existing_installation_data["installations"] + initial_installations_count
            )
            database.increment_installation_count(uuid_to_increment)

    database.add_installation(new_installation_uuid, new_jwt, initial_installations_count)

    return {"jwt": new_jwt}


@app.get("/latest", dependencies=[Depends(verify_token)])
async def get_latest(
    currencies: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    database=Depends(get_db),
):
    target_currencies = currencies or currency
    currency_list = (
        [c.strip().upper() for c in target_currencies.split(",")] if target_currencies else None
    )
    try:
        rates = database.get_latest_rates(currency_list)
        return {"rates": rates}
    except Exception as e:
        print(f"Error handling /latest: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/historical", dependencies=[Depends(verify_token)])
async def get_historical(
    date: str,
    currencies: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    database=Depends(get_db),
):
    if not date:
        raise HTTPException(status_code=400, detail="Bad request: date is required")

    target_currencies = currencies or currency
    currency_list = (
        [c.strip().upper() for c in target_currencies.split(",")] if target_currencies else None
    )
    try:
        rates = database.get_rates_for_date(date, currency_list)
        return {"rates": rates}
    except Exception as e:
        print(f"Error handling /historical: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/currencies", dependencies=[Depends(verify_token)])
async def get_currencies(crypto: Optional[bool] = None, database=Depends(get_db)):
    try:
        cur_list = database.get_currencies(crypto)
        return {"list": cur_list}
    except Exception as e:
        print(f"Error handling /currencies: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/sync/push", dependencies=[Depends(verify_token)])
async def sync_push(request: SyncPushRequest, database=Depends(get_db)):
    try:
        package = request.package
        recipient_keys_list = [rk.model_dump() for rk in package.recipient_keys]

        package_id = database.save_package(
            sender_id=package.sender_id,
            iv=package.iv,
            ciphertext=package.ciphertext,
            recipient_keys=recipient_keys_list,
        )

        sse_manager.notify_many(
            [rk.installation_id for rk in package.recipient_keys],
            "package",
            json.dumps({"package_id": package_id}),
        )
        return {"success": True, "package_id": package_id}
    except Exception as e:
        print(f"Error handling /sync/push: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/sync/events")
async def sync_events(
    installation_id: str = Query(...),
    _=Depends(verify_token),
    database=Depends(get_db),
):
    queue = sse_manager.connect(installation_id)

    async def generator():
        try:
            async for chunk in sse_manager.event_generator(installation_id, queue):
                yield chunk
        finally:
            sse_manager.disconnect(installation_id, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/sync/pull", dependencies=[Depends(verify_token)])
async def sync_pull(
    installation_id: str = Query(...), since: int = Query(0), database=Depends(get_db)
):
    try:
        packages = database.get_packages_for_installation(installation_id, since)
        return {"packages": packages}
    except Exception as e:
        print(f"Error handling /sync/pull: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/sync/ack", dependencies=[Depends(verify_token)])
async def sync_ack(request: SyncAckRequest, database=Depends(get_db)):
    try:
        database.delete_packages(request.package_ids, request.installation_id)
        return {"success": True}
    except Exception as e:
        print(f"Error handling /sync/ack: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/sync/init", dependencies=[Depends(verify_token)])
async def sync_init_get(uuid: str = Query(...), database=Depends(get_db)):
    try:
        packages = database.get_handshake(uuid)
        return packages
    except Exception as e:
        print(f"Error handling GET /sync/init: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/sync/init", dependencies=[Depends(verify_token)])
async def sync_init_post(request: SyncInitRequest, database=Depends(get_db)):
    try:
        database.save_handshake(request.uuid, request.payload)
        sse_manager.notify(request.uuid, "handshake")
        return {"success": True}
    except Exception as e:
        print(f"Error handling GET /sync/init: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.delete("/sync/init", dependencies=[Depends(verify_token)])
async def sync_init_delete(request: SyncInitDelRequest, database=Depends(get_db)):
    try:
        database.delete_handshake(request.ids, request.uuid)
        return {"success": True}
    except Exception as e:
        print(f"Error handling GET /sync/init: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
