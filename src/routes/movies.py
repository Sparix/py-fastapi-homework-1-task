from typing import List
from urllib.request import Request

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db, MovieModel
from src.schemas.movies import MovieDetailResponseSchema, MovieListResponseSchema

router = APIRouter()


# @router.get("/movies/", response_model=List[MoviesGet])
# async def get_movies(db: AsyncSession = Depends(get_db)):
#     movies = await db.execute(select(MovieModel))
#     return movies.scalars().all()

@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1),
        db: AsyncSession = Depends(get_db)
):
    total_result = await db.execute(
        select(func.count()).select_from(MovieModel)
    )
    total_items = total_result.scalar_one()
    total_pages = (total_items + per_page - 1) // per_page

    offset = (page - 1) * per_page
    result = await db.execute(
        select(MovieModel).offset(offset).limit(per_page)
    )
    movies_page = result.scalars().all()

    if not movies_page:
        raise HTTPException(status_code=404, detail="No movies found.")

    if page > total_pages > 0:
        raise HTTPException(status_code=418, detail=[
            {
                "loc": ["query", "page"],
                "msg": "ensure this value is greater than or equal to 1",
                "type": "value_error.number.not_ge"
            }
        ])

    return {
        "movies": [MovieDetailResponseSchema.from_orm(movie) for movie in movies_page],
        "prev_page": f"/theater/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        "next_page": f"/theater/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        "total_pages": total_pages,
        "total_items": total_items
    }


@router.get("/movies/{movie_id}/", response_model=MovieDetailResponseSchema)
async def get_detail_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))

    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return movie
