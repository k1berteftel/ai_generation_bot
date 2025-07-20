from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import db_user, db_pass, db_host, db_name

db_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}/{db_name}"

engine = create_async_engine(db_url, echo=False)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)