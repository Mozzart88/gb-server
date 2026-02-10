import os
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Query, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from .db import db

API_KEY = os.getenv("API_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
security = HTTPBearer()

# Dependency function for database access (enables testing with overrides)
def get_db():
    return db

class RegisterRequest(BaseModel):
    id: str

async def verify_token(auth: HTTPAuthorizationCredentials = Security(security), database = Depends(get_db)):
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
        
        return jwt_from_payload
    except jwt.PyJWTError:
        raise credentials_exception

app = FastAPI(title="Exchange API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/register")
async def register(request: RegisterRequest, uuid_to_increment: Optional[str] = Query(None, alias="uuid"), database = Depends(get_db)):
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY is not configured")

    new_installation_uuid = request.id
    
    # Generate new JWT
    expire = datetime.now(timezone.utc) + timedelta(days=365)
    to_encode = {"jwt": str(uuid.uuid4()), "issued": datetime.now(timezone.utc).isoformat(), "exp": expire.timestamp()}
    new_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")

    initial_installations_count = 1
    if uuid_to_increment:
        existing_installation_data = database.get_installation_by_uuid(uuid_to_increment)
        if existing_installation_data:
            initial_installations_count = existing_installation_data["installations"] + initial_installations_count
            database.increment_installation_count(uuid_to_increment)

    database.add_installation(new_installation_uuid, new_jwt, initial_installations_count)
    
    return {"jwt": new_jwt}

@app.get("/latest", dependencies=[Depends(verify_token)])
async def get_latest(currencies: Optional[str] = Query(None), currency: Optional[str] = Query(None), database = Depends(get_db)):
    target_currencies = currencies or currency
    currency_list = [c.strip().upper() for c in target_currencies.split(",")] if target_currencies else None
    try:
        rates = database.get_latest_rates(currency_list)
        return {"rates": rates}
    except Exception as e:
        print(f"Error handling /latest: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/historical", dependencies=[Depends(verify_token)])
async def get_historical(date: str, currencies: Optional[str] = Query(None), currency: Optional[str] = Query(None), database = Depends(get_db)):
    if not date:
        raise HTTPException(status_code=400, detail="Bad request: date is required")
    
    target_currencies = currencies or currency
    currency_list = [c.strip().upper() for c in target_currencies.split(",")] if target_currencies else None
    try:
        rates = database.get_rates_for_date(date, currency_list)
        return {"rates": rates}
    except Exception as e:
        print(f"Error handling /historical: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/currencies", dependencies=[Depends(verify_token)])
async def get_currencies(crypto: Optional[bool] = None, database = Depends(get_db)):
    try:
        cur_list = database.get_currencies(crypto)
        return {"list": cur_list}
    except Exception as e:
        print(f"Error handling /currencies: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
