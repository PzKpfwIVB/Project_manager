from typing import Annotated

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import Depends

from application.core.config import DATABASE_URL

# Preemptively checking for a dropped connection with `pool_pre_ping`
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


def get_session():
    with Session() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]
