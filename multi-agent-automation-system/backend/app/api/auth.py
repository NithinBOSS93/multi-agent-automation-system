from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import create_token, hash_password, require_user, verify_password
from app.db.database import get_db, now

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=128)


@router.post("/register")
async def register(body: Credentials):
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM users WHERE username = ?", (body.username,))
        if await cur.fetchone():
            raise HTTPException(400, "Username already taken")
        cur = await db.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (body.username, hash_password(body.password), now()),
        )
        await db.commit()
        user_id = cur.lastrowid
    return {"token": create_token(user_id, body.username), "username": body.username}


@router.post("/login")
async def login(body: Credentials):
    async with get_db() as db:
        cur = await db.execute("SELECT id, password_hash FROM users WHERE username = ?", (body.username,))
        row = await cur.fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong username or password")
    return {"token": create_token(row["id"], body.username), "username": body.username}


@router.get("/me")
async def me(user: dict = Depends(require_user)):
    return {"id": int(user["sub"]), "username": user["username"]}
