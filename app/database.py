from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_missing_columns(bind=None):
    """
    Thêm các cột mới (khai báo trong model) vào bảng đã có sẵn trong CSDL.
    create_all() chỉ tạo bảng mới, không thêm cột cho bảng cũ, nên file qlcl.db
    tạo từ sprint trước sẽ thiếu cột. Hàm này giúp không phải xóa qlcl.db.
    """
    from sqlalchemy import inspect, text
    bind = bind or engine
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                col_type = col.type.compile(dialect=bind.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}'))
