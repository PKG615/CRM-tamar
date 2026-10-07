from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator

from app.models import UserRole

# bcrypt only looks at the first 72 bytes; cap the length instead of silently truncating
Password = Field(min_length=8, max_length=72)


class OrgRegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=255)
    admin_name: str = Field(min_length=1, max_length=255)
    admin_email: EmailStr
    admin_password: str = Password

    @field_validator("admin_email")
    @classmethod
    def lower_email(cls, v):
        return v.lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_slug: str  # which tenant to log into

    @field_validator("email")
    @classmethod
    def lower_email(cls, v):
        return v.lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: Optional[datetime] = None


class UserDirectoryEntry(BaseModel):
    """Minimal fields any team member may see (for assignee dropdowns)."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    role: UserRole


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    role: UserRole = UserRole.SALES_EXECUTIVE
    # Optional: if omitted, the user is invited by email (set-password link)
    # when SMTP is configured; otherwise a temporary password is generated
    # and returned once so the admin can share it directly.
    password: Optional[str] = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, v):
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_length(cls, v):
        if v is not None and not (8 <= len(v) <= 72):
            raise ValueError("password must be 8-72 characters")
        return v


class UserCreateResult(BaseModel):
    """UserOut plus one-time invite info the frontend needs to show once."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str
    role: UserRole
    is_active: bool
    invited_by_email: bool = False
    temporary_password: Optional[str] = None  # only set when email couldn't be sent


class ForgotPasswordRequest(BaseModel):
    organization_slug: str
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lower_email(cls, v):
        return v.lower()


class SetPasswordRequest(BaseModel):
    token: str
    new_password: str = Password


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str = Password


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Password
