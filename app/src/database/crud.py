import database.models as models
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

async def async_db_save(db:AsyncSession,prompt, response,message_type,thread_id):
    try:

        print("Saving\n")
        agent_history = models.AgentHistory(prompt=prompt,response=response,message_type=message_type,thread_id=thread_id)
        db.add(agent_history)
        await db.commit()
        await db.refresh(agent_history)
        print("save successful\n")


        return agent_history
    
    except SQLAlchemyError as e:
        raise RuntimeError(f"Database Savings failed: {str(e)}")