import pycountry

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from typing import Type
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db, MovieModel, Base
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas.movies import ReadMovie

from schemas.movies import CreateMovie

from schemas.movies import ResponseMovie

from schemas.movies import UpdateMovie

router = APIRouter()


@router.get("/movies/", response_model=ReadMovie)
async def get_film(page: int = 1, per_page: int = 10, db: AsyncSession = Depends(get_db)):
    if page < 1:
        raise HTTPException(status_code=422, detail="Page must be greater than or equal 1")
    if per_page < 1 or per_page > 20:
        raise HTTPException(status_code=422, detail="Per page must be in range 1-20 (incl.)")

    result = await db.execute(func.count(MovieModel.id))
    movies_list_count = result.scalar()

    if not movies_list_count or movies_list_count == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = (movies_list_count // per_page) + (1 if movies_list_count % per_page != 0 else 0)
    prev_page = None if page == 1 else f"/theater/movies/?page={page - 1}&per_page={per_page}"
    next_page = None if page == total_pages else f"/theater/movies/?page={page + 1}&per_page={per_page}"

    offset = (page - 1) * per_page

    result = await db.execute(select(MovieModel).offset(offset).limit(per_page).order_by(MovieModel.id.desc()))
    movies_list = result.scalars().all()

    return {
        "movies": [
            {
                "id": movie.id,
                "name": movie.name,
                "date": movie.date,
                "score": movie.score,
                "overview": movie.overview
            } for movie in movies_list
        ],
        "prev_page": prev_page,
        "next_page": next_page,
        "total_pages": total_pages,
        "total_items": movies_list_count
    }


@router.post("/movies/", response_model=ResponseMovie)
async def create_film(film: CreateMovie, db: AsyncSession = Depends(get_db)):
    country_obj = await create_value_in_db_if_not_exists_and_return_none_if_exists(
        value_name=film.country,
        model=CountryModel,
        db=db
    )
    genre_objs = await create_value_in_db_if_not_exists_and_return_none_if_exists(
        value_name=film.genres,
        model=GenreModel,
        db=db
    )
    actors_objs = await create_value_in_db_if_not_exists_and_return_none_if_exists(
        value_name=film.actors,
        model=ActorModel,
        db=db
    )
    languages_objs = await create_value_in_db_if_not_exists_and_return_none_if_exists(
        value_name=film.languages,
        model=LanguageModel,
        db=db
    )
    result_movie_and_date = await db.execute(select(MovieModel.name, MovieModel.date))
    movie_names_and_dates = result_movie_and_date.fetchall()

    for name, date in movie_names_and_dates:
        if film.date == date and film.name == name:
            raise HTTPException(status_code=422, detail=f"A movie with the name '{name}' "
                                                        f"and release date '{date}' already exists.")
    if not film:
        raise HTTPException(status_code=400, detail="Invalid data were given.")

    new_film_data = film.dict()

    new_film_data.pop("country")
    new_film_data.pop("actors")
    new_film_data.pop("genres")
    new_film_data.pop("languages")

    new_film = MovieModel(**new_film_data)

    new_film.country = country_obj
    new_film.actors = actors_objs
    new_film.genres = genre_objs
    new_film.languages = languages_objs

    db.add(new_film)
    await db.commit()
    await db.refresh(new_film)

    return new_film


@router.get("/movies/{movie_id}/", response_model=ResponseMovie)
async def get_film_by_id(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MovieModel).options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages)
        ).where(MovieModel.id == movie_id)
    )
    film = result.scalar_one_or_none()

    if not film:
        raise HTTPException(status_code=404, detail="Movie with the given ID wos not found.")
    return film


@router.delete("/movies/{movie_id}/")
async def delete_film(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    film_to_delete = result.scalar_one_or_none()
    if not film_to_delete:
        return None
    await db.delete(film_to_delete)
    await db.commit()


@router.patch("/movies/{movie_id}/", status_code=status.HTTP_200_OK)
async def update_movie(movie_id: int, film: UpdateMovie, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()

    score_validate = True if film.score >= 0 and film.score <= 100 else False
    budget_validate = True if film.budget >= 0 else False
    revenue_validate = True if film.revenue >= 0 else False

    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    if not film or not score_validate or not budget_validate or not revenue_validate:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    if movie.name is not None:
        movie.name = film.name
    if movie.date is not None:
        movie.date = film.date
    if movie.score is not None:
        movie.score = film.score
    if movie.overview is not None:
        movie.overview = film.overview
    if movie.status is not None:
        movie.status = film.status
    if movie.budget is not None:
        movie.budget = film.budget
    if movie.revenue is not None:
        movie.revenue = film.revenue

    await db.commit()
    await db.refresh(movie)

    return {
        "detail": "Movie updated successfully."
    }


async def create_value_in_db_if_not_exists_and_return_none_if_exists(
        value_name: str | list,
        model: Type[Base],
        db: AsyncSession
):
    if isinstance(value_name, str):
        result = await db.execute(select(model).filter(model.code == value_name))
        value = result.scalar_one_or_none()
        if value:
            return value

        country_name = get_country_name(code=value_name)
        new_value = model(code=value_name, name=country_name)
        db.add(new_value)
        await db.commit()
        await db.refresh(new_value)
        return new_value


    elif isinstance(value_name, list):
        result = await db.execute(select(model).filter(model.name.in_(value_name)))
        values = result.scalars().all()
        existing_values = {getattr(inst, "name") for inst in values}

        new_instances = []
        existing_instances = []

        for name in value_name:
            if name not in existing_values:
                new_value = model(name=name)
                db.add(new_value)
                new_instances.append(new_value)
            else:
                for inst in values:
                    if inst.name == name:
                        existing_instances.append(inst)

        if new_instances:
            await db.commit()
            for created_value in new_instances:
                await db.refresh(created_value)

        return new_instances + existing_instances

    return None


def get_country_name(code: str) -> str | None:
    country = pycountry.countries.get(alpha_3=code)
    if country:
        return country.name
    return None
