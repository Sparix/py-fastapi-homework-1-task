import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from tqdm.asyncio import tqdm

from src.config import get_settings
from src.database import MovieModel, get_db_contextmanager, init_db


class CSVDatabaseSeeder:
    """
    Class responsible for seeding the database with movie data from a CSV file.

    Attributes:
        _csv_file_path (str): Path to the CSV file containing movie data.
        _db_session (AsyncSession): Asynchronous SQLAlchemy session for database operations.
    """

    def __init__(self, csv_file_path: str, db_session: AsyncSession):
        """
        Initialize the CSVDatabaseSeeder with a file path and an async database session.

        :param csv_file_path: Path to the CSV file containing movie data.
        :type csv_file_path: str
        :param db_session: Async database session for executing queries.
        :type db_session: AsyncSession
        """
        self._csv_file_path = csv_file_path
        self._db_session = db_session

    async def is_db_populated(self) -> bool:
        """
        Check if the movie database already contains records.

        :return: True if the database contains at least one record, False otherwise.
        :rtype: bool
        """
        result = await self._db_session.execute(select(func.count()).select_from(MovieModel))
        total_count = result.scalar_one()
        return total_count > 0

    async def _preprocess_csv(self) -> pd.DataFrame:
        """
        Load and preprocess the CSV file before inserting data into the database.

        The function removes duplicate records based on 'names' and 'date_x',
        replaces missing values, trims whitespace, and converts dates to a standard format.

        :return: Preprocessed DataFrame containing the movie data.
        :rtype: pd.DataFrame
        """
        data = pd.read_csv(self._csv_file_path)
        data = data.drop_duplicates(subset=['names', 'date_x'], keep='first')
        data['crew'] = data['crew'].fillna('Unknown')
        data['genre'] = data['genre'].fillna('Unknown')
        data['genre'] = data['genre'].str.replace('\u00A0', '', regex=True)
        data['date_x'] = data['date_x'].str.strip()
        data['date_x'] = pd.to_datetime(data['date_x'], format='%m/%d/%Y', errors='coerce')
        data['date_x'] = data['date_x'].dt.date
        print("Preprocessing csv file")
        return data

    async def seed(self) -> None:
        """
        Seed the database with movie data from the CSV file.

        The function reads the CSV, processes the data, and inserts it into the database.
        It ensures that no duplicate records are inserted, and commits the transaction.

        :raises SQLAlchemyError: If an error occurs during database operations.
        :raises Exception: If any unexpected error occurs.
        """
        try:
            if self._db_session.in_transaction():
                print("Rolling back existing transaction.")
                await self._db_session.rollback()

            data = await self._preprocess_csv()

            async with self._db_session.begin():
                for _, row in tqdm(data.iterrows(), total=data.shape[0], desc="Seeding database"):
                    movie = MovieModel(
                        name=row['names'],
                        date=row['date_x'],
                        score=float(row['score']),
                        genre=row['genre'],
                        overview=row['overview'],
                        crew=row['crew'],
                        orig_title=row['orig_title'],
                        status=row['status'],
                        orig_lang=row['orig_lang'],
                        budget=float(row['budget_x']),
                        revenue=float(row['revenue']),
                        country=row['country']
                    )
                    self._db_session.add(movie)

            await self._db_session.commit()
        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
            await self._db_session.rollback()
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            await self._db_session.rollback()
            raise


async def main() -> None:
    """
    Entry point for the database seeding process.

    This function initializes the database (if necessary) and seeds it with movie data.
    It checks whether the database is already populated to prevent duplicate insertions.

    If the database is empty, it proceeds with the seeding process.
    Otherwise, it prints a message and exits.

    :return: None
    """
    settings = get_settings()

    await init_db()

    async with get_db_contextmanager() as db_session:
        seeder = CSVDatabaseSeeder(settings.PATH_TO_MOVIES_CSV, db_session)

        if not await seeder.is_db_populated():
            try:
                await seeder.seed()
                print("Database seeding completed successfully.")
            except Exception as e:
                print(f"Failed to seed the database: {e}")
        else:
            print("Database is already populated. Skipping seeding.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
