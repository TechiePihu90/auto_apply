import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, String, Boolean, DateTime, Text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./auto_apply.db")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Application(Base):
    __tablename__ = "applications"
    id              = Column(String, primary_key=True)
    user_id         = Column(String, index=True)
    job_id          = Column(String)
    platform        = Column(String)
    success         = Column(Boolean)
    confirmation_id = Column(String, default="")
    error           = Column(Text, default="")
    applied_at      = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def save_result(user_id: str, job_id: str, result):
    await init_db()
    import uuid
    async with AsyncSessionLocal() as session:
        app = Application(
            id=str(uuid.uuid4()),
            user_id=user_id,
            job_id=job_id,
            platform=result.platform,
            success=result.success,
            confirmation_id=result.confirmation_id,
            error=result.error,
        )
        session.add(app)
        await session.commit()

async def get_results(user_id: str):
    await init_db()
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Application).where(Application.user_id == user_id)
                               .order_by(Application.applied_at.desc())
        )
        apps = rows.scalars().all()
        return [
            {
                "job_id":          a.job_id,
                "platform":        a.platform,
                "success":         a.success,
                "confirmation_id": a.confirmation_id,
                "error":           a.error,
                "applied_at":      a.applied_at.isoformat(),
            }
            for a in apps
        ]
