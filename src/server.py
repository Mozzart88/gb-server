import os
from fastapi import FastAPI, HTTPException, Query, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from .db import db

API_KEY = os.getenv("API_KEY")
security = HTTPBearer()

async def verify_token(auth: HTTPAuthorizationCredentials = Security(security)):
    if API_KEY and auth.credentials != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return auth.credentials

app = FastAPI(title="Exchange API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/latest", dependencies=[Depends(verify_token)])
async def get_latest(currencies: Optional[str] = Query(None), currency: Optional[str] = Query(None)):
    target_currencies = currencies or currency
    currency_list = [c.strip().upper() for c in target_currencies.split(",")] if target_currencies else None
    try:
        rates = db.get_latest_rates(currency_list)
        return {"rates": rates}
    except Exception as e:
        print(f"Error handling /latest: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/historical", dependencies=[Depends(verify_token)])
async def get_historical(date: str, currencies: Optional[str] = Query(None), currency: Optional[str] = Query(None)):
    if not date:
        raise HTTPException(status_code=400, detail="Bad request: date is required")
    
    target_currencies = currencies or currency
    currency_list = [c.strip().upper() for c in target_currencies.split(",")] if target_currencies else None
    try:
        rates = db.get_rates_for_date(date, currency_list)
        return {"rates": rates}
    except Exception as e:
        print(f"Error handling /historical: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/currencies", dependencies=[Depends(verify_token)])
async def get_currencies(crypto: Optional[bool] = None):
    try:
        cur_list = db.get_currencies(crypto)
        return {"list": cur_list}
    except Exception as e:
        print(f"Error handling /currencies: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
