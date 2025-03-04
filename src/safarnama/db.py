from datetime import datetime, timedelta  # Fixed: import timedelta from datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger
from typing import List

Base = declarative_base()


# ------------------------------
# URL Model for the Crawler
# ------------------------------
class URL(Base):
    __tablename__ = "urls"
    url = Column(String, primary_key=True)
    depth = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    content_type = Column(String)
    summary = Column(Text)
    tags = Column(Text)


# ------------------------------
# Instance Model for Searcher
# ------------------------------
class Instance(Base):
    __tablename__ = "instances"
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    version = Column(String)
    tls = Column(String)
    csp = Column(String)
    html = Column(String)
    certificate = Column(String)
    ipv6 = Column(String)
    country = Column(String)
    network = Column(String)
    search_response_time = Column(Float)
    google_response_time = Column(Float)
    initial_response_time = Column(Float)
    uptime = Column(Float)
    priority = Column(Integer, default=100)
    sleep_until = Column(DateTime)


# ------------------------------
# Unified Database Handler
# ------------------------------
class DBHandler:
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    # ----- Methods for URL table -----
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

    # ----- Methods for Instances table (used by searcher) -----
    def upsert_instance(self, instance: dict, url: str):
        session = self.Session()
        try:
            record = session.query(Instance).filter_by(url=url).first()
            version = instance.get("version")
            tls = instance.get("tls", {}).get("grade")
            csp = instance.get("http", {}).get("grade")
            html = instance.get("html", {}).get("grade")
            certificate = (
                instance.get("tls", {})
                .get("certificate", {})
                .get("issuer", {})
                .get("commonName")
            )
            ipv6 = "Yes" if instance.get("network", {}).get("ipv6") else "No"
            country = instance.get("country")
            network = instance.get("network_type")
            search_rt = (
                instance.get("timing", {})
                .get("search", {})
                .get("all", {})
                .get("median")
            )
            google_rt = (
                instance.get("timing", {})
                .get("search_go", {})
                .get("all", {})
                .get("median")
            )
            initial_rt = (
                instance.get("timing", {})
                .get("initial", {})
                .get("all", {})
                .get("value")
            )
            uptime = instance.get("uptime", {}).get("uptimeYear")
            if record:
                record.version = version
                record.tls = tls
                record.csp = csp
                record.html = html
                record.certificate = certificate
                record.ipv6 = ipv6
                record.country = country
                record.network = network
                record.search_response_time = search_rt
                record.google_response_time = google_rt
                record.initial_response_time = initial_rt
                record.uptime = uptime
            else:
                record = Instance(
                    url=url,
                    version=version,
                    tls=tls,
                    csp=csp,
                    html=html,
                    certificate=certificate,
                    ipv6=ipv6,
                    country=country,
                    network=network,
                    search_response_time=search_rt,
                    google_response_time=google_rt,
                    initial_response_time=initial_rt,
                    uptime=uptime,
                    priority=100,
                    sleep_until=None,
                )
                session.add(record)
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error upserting instance {url}: {e}")
        finally:
            session.close()

    def update_sleep(self, url: str, sleep_seconds: int):
        session = self.Session()
        try:
            record = session.query(Instance).filter_by(url=url).first()
            if record:
                record.sleep_until = datetime.utcnow() + timedelta(
                    seconds=sleep_seconds
                )
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating sleep for instance {url}: {e}")
        finally:
            session.close()

    def clear_sleep(self, url: str):
        session = self.Session()
        try:
            record = session.query(Instance).filter_by(url=url).first()
            if record:
                record.sleep_until = None
                session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error clearing sleep for instance {url}: {e}")
        finally:
            session.close()

    def update_all_priorities(self):
        session = self.Session()
        try:
            records = session.query(Instance).all()
            for record in records:
                new_priority = 100 - (record.uptime or 0)
                record.priority = new_priority
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating priorities: {e}")
        finally:
            session.close()

    def get_available_instances(self) -> List[Instance]:
        session = self.Session()
        try:
            now = datetime.utcnow()
            records = (
                session.query(Instance)
                .filter((Instance.sleep_until is None) | (Instance.sleep_until <= now))
                .order_by(Instance.priority.asc())
                .all()
            )
            return records
        except SQLAlchemyError as e:
            logger.error(f"Error fetching available instances: {e}")
            return []
        finally:
            session.close()

    def close(self):
        pass
