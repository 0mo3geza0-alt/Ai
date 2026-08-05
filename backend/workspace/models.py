from typing import Optional
from pydantic import BaseModel


class ProjectBody(BaseModel):
    name: str
    description: Optional[str] = ""


class ArtifactBody(BaseModel):
    name: str
    type: str = "text"
    content: str = ""
