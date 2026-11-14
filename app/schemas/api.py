from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    contract_count: int = 0


class ContractRename(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ContractQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=10000)
    conversation_id: str | None = None


class ProjectQuestion(ContractQuestion):
    pass


class TranslateRequest(BaseModel):
    target_language: str = Field(pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
    source_language: str | None = Field(default=None, pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
    scope: str = Field(default="contract", pattern="^(contract|summary)$")


class CompareRequest(BaseModel):
    first_version_id: str
    second_version_id: str


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
