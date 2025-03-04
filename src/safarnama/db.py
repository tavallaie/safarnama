from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

Base = declarative_base()

# We no longer need the vector field, so we remove UniversalVector.


class URL(Base):
    __tablename__ = "urls"
    url = Column(String, primary_key=True)
    depth = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    content_type = Column(String)
    summary = Column(Text)
    tags = Column(Text)


class DBHandler:
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def insert_url(self, url: str, depth: int, status: str, content_type: str = None):
        session = self.Session()
        try:
            record = URL(url=url, depth=depth, status=status, content_type=content_type)
            session.add(record)
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error inserting URL {url}: {e}")
        finally:
            session.close()

    def update_url_status(self, url: str, status: str, content_type: str = None):
        session = self.Session()
        try:
            record = session.query(URL).filter_by(url=url).first()
            if record:
                record.status = status
                record.content_type = content_type
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating URL status for {url}: {e}")
        finally:
            session.close()

    def update_page_info(self, url: str, summary: str, tags: str):
        session = self.Session()
        try:
            record = session.query(URL).filter_by(url=url).first()
            if record:
                record.summary = summary
                record.tags = tags
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating page info for {url}: {e}")
        finally:
            session.close()

    def get_next_url(self, max_depth: int) -> tuple:
        session = self.Session()
        try:
            record = (
                session.query(URL)
                .filter(URL.status == "to_visit", URL.depth <= max_depth)
                .order_by(URL.depth)
                .first()
            )
            if record:
                return record.url, record.depth
            else:
                return None, None
        except SQLAlchemyError as e:
            logger.error(f"Error fetching next URL: {e}")
            return None, None
        finally:
            session.close()

    def close(self):
        pass
