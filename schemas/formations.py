from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class CompetenceSchema(BaseModel):
    name: str = Field(..., alias="x_name")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SignataireSchema(BaseModel):
    name: str = Field(..., alias="x_name")
    role: str = Field(..., alias="x_studio_role")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ParticipantSchema(BaseModel):
    id: str = Field(..., alias="x_studio_numero_de_certificat")
    name: str = Field(..., alias="x_name")
    title: str = Field(..., alias="x_studio_titre_professionnel")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class FormationSchema(BaseModel):
    id: str = Field(..., alias="x_studio_identifiant_code")
    title: str = Field(..., alias="x_name")
    shortTitle: Optional[str] = Field(None, alias="x_studio_titre_court")
    status: str = Field(..., alias="x_studio_statut")
    dateRange: Optional[str] = Field(None, alias="x_studio_dates_texte")
    duration: Optional[str] = Field(None, alias="x_studio_duree")
    location: Optional[str] = Field(None, alias="x_studio_lieu")
    certifNumPrefix: Optional[str] = Field(None, alias="x_studio_prefixe_certificat")
    description: Optional[str] = Field(None, alias="x_studio_description")
    partners: List[str] = Field(default_factory=list, alias="x_studio_partenaires")
    competences: List[str] = Field(default_factory=list, alias="x_studio_competences_visees")
    signataires: List[SignataireSchema] = Field(default_factory=list, alias="x_studio_signataires")
    participants: List[ParticipantSchema] = Field(default_factory=list, alias="x_studio_participant_ids")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
