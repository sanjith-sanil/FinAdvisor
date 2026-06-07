import uuid

from pydantic import BaseModel, EmailStr, Field


class AuthRegister(BaseModel):
    full_name: str = Field(max_length=255)
    email: EmailStr
    phone_number: str = Field(max_length=15)
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)


class AuthLogin(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: uuid.UUID
    customer_id: str
    full_name: str
    email: EmailStr
