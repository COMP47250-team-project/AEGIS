import uuid
from pydantic import BaseModel


# Request schemas
class CourseCreate(BaseModel):
    name: str
    access_code: str


class EnrollRequest(BaseModel):
    access_code: str


# Response schemas
class StudentResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str

    class Config:
        from_attributes = True


class CourseResponse(BaseModel):
    id: uuid.UUID
    name: str
    access_code: str

    class Config:
        from_attributes = True
