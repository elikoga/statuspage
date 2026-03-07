import pathlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from statuspage.config import global_settings


def get_db_url() -> str:
    db_path: pathlib.Path = global_settings.DATA_PATH / "statuspage.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def create_sqlalchemy_engine():
    return create_engine(
        get_db_url(),
        connect_args={"check_same_thread": False},
    )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=None)


def get_db():
    from statuspage.main import db_engine

    session = SessionLocal(bind=db_engine)
    try:
        yield session
    finally:
        session.close()
