from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    student_id: int | None = None  # linked student (own record, or the child for a parent)


class RiskOut(BaseModel):
    student_id: int
    roll_no: str
    name: str
    risk_level: str
    probability: float  # risk index 0-1: P(High) + 0.5 * P(Medium)
    features: dict
    factors: list[dict]
    created_at: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
