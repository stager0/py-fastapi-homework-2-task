import pycountry

from fastapi import Depends
from pydantic import BaseModel, validator, Field
from datetime import datetime, timedelta
from typing import Optional, List, Type, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from database.models import MovieModel
from database import get_db, Base


class MovieBase(BaseModel):
    id: int
    name: str
    date: datetime
    score: float
    overview: str

    class Config:
        from_attributes = True
        from_orm=True
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d")
        }


class ReadMovie(BaseModel):
    movies: List[MovieBase]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int


class ItemGenre(BaseModel):
    name: str

    class Config:
        from_attributes: True


class ReadGenre(ItemGenre):
    id: int


class ItemCountry(BaseModel):
    code: str

    class Config:
        from_attributes: True


class ReadCountry(ItemCountry):
    id: int


class ItemActors(BaseModel):
    name: str

    class Config:
        from_attributes: True


class ReadActors(ItemActors):
    id: int


class ItemLanguage(BaseModel):
    name: str

    class Config:
        from_attributes: True


class ReadLanguage(ItemLanguage):
    id: int
    name: str


class CreateMovie(BaseModel):
    name: str = Field(max_length=255)
    date: datetime
    score: float = Field(ge=0, le=100)
    overview: str
    status: str
    budget: float = Field(gt=0)
    revenue: float = Field(gt=0)
    country: str
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @validator("date")
    def validate_date(cls, value):
        one_year_in_the_future = datetime.now() + timedelta(days=365)
        if value > one_year_in_the_future:
            raise ValueError("The date must be less than in one year in the future")
        return value


class ResponseMovie(MovieBase):
    status: str
    budget: float
    revenue: float
    country: ReadCountry
    genres: List[ReadGenre]
    actors: List[ReadActors]
    languages: List[ReadLanguage]


class UpdateMovie(BaseModel):
    name: Optional[str] = None
    date: Optional[datetime] = None
    score: Optional[float] = None
    overview: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[float] = None
    revenue: Optional[float] = None

    class Config:
        from_attributes=True
        from_orm=True
        json_encoders = {
            datetime: lambda value: value.strftime("%Y-%m-%d")
        }