from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine, text

DATABASE_URL = "sqlite:///./social_planner.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(post)")).fetchall()}
        if "image_path" not in existing:
            conn.execute(text("ALTER TABLE post ADD COLUMN image_path TEXT"))
            conn.commit()
        if "phrase" not in existing:
            conn.execute(text("ALTER TABLE post ADD COLUMN phrase TEXT"))
            conn.commit()
        if "font" not in existing:
            conn.execute(text("ALTER TABLE post ADD COLUMN font TEXT"))
            conn.commit()
        if "overlay_style" not in existing:
            conn.execute(text("ALTER TABLE post ADD COLUMN overlay_style TEXT"))
            conn.commit()


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session
