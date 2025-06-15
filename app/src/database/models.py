from database.db import Base
from sqlalchemy import Column, String, Boolean, Integer,TIMESTAMP,UUID
from datetime import datetime, timezone
import uuid
from sqlalchemy.sql import func

class AgentHistory(Base):
    __tablename__ = "agent_history"
    id = Column(UUID(as_uuid=True), primary_key=True, nullable=False,default=uuid.uuid4)
    prompt=Column(String)
    response = Column(String)
    message_type = Column(String)
    thread_id = Column(String)
    created_at = Column(TIMESTAMP(timezone=True),nullable=False, default=lambda:datetime.now(timezone.utc),server_default=func.now())



