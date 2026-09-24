import os

from alembic import context

from backend.app.v2.models import Base
from backend.app.v2.runtime import database_engine

url = os.getenv("DATABASE_URL", context.config.get_main_option("sqlalchemy.url"))
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = database_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_object=lambda obj, name, type_, reflected, compare_to: (
                name.startswith("invoice_v2_") if type_ == "table" else True
            ),
        )
        with context.begin_transaction():
            context.run_migrations()
