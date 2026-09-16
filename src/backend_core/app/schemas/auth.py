from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User display name")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Password must be at least 8 characters long",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Name cannot be empty or only whitespace")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password cannot exceed 72 bytes in UTF-8 encoding.")
        if len(value.strip()) < 8:
            raise ValueError("Password must be at least 8 characters and cannot be only whitespace.")
        if len(set(value)) < 4:
            raise ValueError("Password must contain at least 4 unique characters.")
        return value


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, max_length=72, description="User password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: uuid.UUID


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
