from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProcessCreate(BaseModel):
    name: str
    description: str | None = None


class ProcessRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
