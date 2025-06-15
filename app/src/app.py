import os
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any,TypedDict, Annotated
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import gc
import logging
import sys
from langchain_core.runnables import RunnableConfig
from llm.llm_services import async_generate_text_response,check_server_status
from agent import react_graph
import json
from fastapi.responses import StreamingResponse
from langchain_core.load import dumpd, dumps, load, loads

from database.db import AsyncSessionLocal, engine, get_async_db_session,Base
from sqlalchemy.ext.asyncio import AsyncSession
from database.crud import async_db_save
import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine
from langgraph.types import Command
import traceback
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)


load_dotenv()


logging.basicConfig(
    level=logging.DEBUG,  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Create a logger instance
logger = logging.getLogger(__name__) # app name


async def create_all_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)



class Message(TypedDict):
    role: str
    content: str

# Define request and response models using Pydantic
class GenerationRequest(BaseModel):
    prompt: List[Message]
    config: Dict
    # Add other parameters as needed for sampling
    # max_new_tokens: int = Field(default=1024, description="Maximum number of tokens to generate.") # Increased max tokens
    # temperature: float = Field(default=0.7, description="Sampling temperature.")
    # top_p: float = Field(default=0.95, description="Top-p sampling.")
    # tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of tools available for tool calling.")
    # tool_choice: str = Field(default="auto", description="Tool choice mode ('auto', 'none', or {'type': 'function', 'function': {'name': 'tool_name'}})")
    class Config:
        from_attributes = True # orm_mode

class ResumeGenerationRequest(BaseModel):
    prompt: List[Message]
    resume: Dict
    config: Dict

    class Config:
        from_attributes = True # orm_mode


class GenerationResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, description="Detected tool calls.")
    finish_reason: Optional[str] = Field(default=None, description="Reason the generation finished.")

    class Config:
        from_attributes = True # orm_mode
        




@asynccontextmanager
async def startup_event(app: FastAPI):
    logger.info("Starting application...")

    logger.info("Creating all tables...")
    await create_all_tables(engine)
    logger.info("Tables created.")

    yield

    logger.info("Application is shutting down...")


app = FastAPI(lifespan=startup_event)


# a custom health-check endpoint
@app.get("/health")
async def health():
    status = check_server_status()
    return status
    



@app.post("/initiate-workflow")
async def initiate_workflow(request: GenerationRequest,db:Annotated[AsyncSession, Depends(get_async_db_session)]):
    """Initiates action workflow."""
    
    input_prompt = request.prompt # list
    config = request.config
    print(f"Initiating workflow for thread_id: {config["configurable"]["thread_id"]} with prompt: {input_prompt}")
    print(input_prompt)

    # gather all response and send them back at once
    response = []
    async for item in react_graph.async_astream_react_agent(input_prompt,config):
        print("initiate item:",item)
        

        if isinstance(item, SystemMessage): # if provided one
            message_type="system"
            item_content = item.content
        elif isinstance(item, HumanMessage):
            message_type="user"
            item_content = item.content
        elif isinstance(item, AIMessage):
            message_type="assistant"
            item_content = item.content
        elif isinstance(item, ToolMessage):
            message_type="tool"
            item_content = item.content
        else:
            message_type = str(type(item))
            item_content = f"{item}"

        

        try:
            agent_history = await async_db_save(db,prompt=input_prompt[0]["content"], response=item_content, message_type=message_type,thread_id=config["configurable"]["thread_id"])
        except Exception as db_error:
            logging.info("DB ERROR CAUGHT:", db_error)
            raise HTTPException(status_code=500,detail=str(db_error))
        
        serialized_item = dumpd(item) # serialize to dict
        response.append(serialized_item)
    print("check_response:",{"response":response})
    return {"response":response}


@app.post("/resume-workflow")
async def resume_workflow(request: ResumeGenerationRequest,db:Annotated[AsyncSession, Depends(get_async_db_session)]):
    """Resumes action workflow."""
    
    resume_command = request.resume # list
    config = request.config
    input_prompt = request.prompt
    print(f"Resuming workflow for thread_id: {config["configurable"]["thread_id"]} with human feedback: {resume_command}")
    

    if resume_command["action"]=="continue":
        human_command = Command(resume={"action": resume_command["action"]})
    else:
        human_command = Command(resume={"action": resume_command["action"],"data":resume_command["data"]})
    print(human_command)
    # gather all response and send them back at once
    response = []
    async for item in react_graph.async_astream_command(human_command,config):
        print("resume item:",item)

        if isinstance(item, SystemMessage): # if provided one
            message_type="system"
            item_content = item.content
        elif isinstance(item, HumanMessage):
            message_type="user"
            item_content = item.content
        elif isinstance(item, AIMessage):
            message_type="assistant"
            item_content = item.content
        elif isinstance(item, ToolMessage):
            message_type="tool"
            item_content = item.content
        else:
            message_type = str(type(item))
            item_content = f"{item}"

        try:
            agent_history = await async_db_save(db,prompt=input_prompt[0]["content"],response=item_content,message_type=message_type,thread_id=config["configurable"]["thread_id"])
        except Exception as db_error:
            logging.info("DB ERROR CAUGHT:", db_error)
            raise HTTPException(status_code=500,detail=str(db_error))
        
        serialized_item = dumpd(item) # serialize to dict
        response.append(serialized_item)

    print("check_response:",{"response":response})
    return {"response":response}



@app.post("/generate-text")
async def generate_text(request: GenerationRequest,db:Annotated[AsyncSession, Depends(get_async_db_session)]):
    """Generates text using the loaded model in vllm server."""
    input_prompt = request.prompt
    print("input:",input_prompt)

    try:
        response = await async_generate_text_response(input_prompt)
        print("response:",response.content)        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")
    
    try:
        agent_history = await async_db_save(db,prompt=input_prompt[0]["content"], response=response.content)
    except Exception as db_error:
        logging.info("DB ERROR CAUGHT:", db_error)
        raise HTTPException(status_code=500,detail=str(db_error))
    
    return {"response":response}




# ----------------------------------- In development -------------------------------------------------    
@app.post("/initiate-workflow-stream")
async def initiate_workflow_stream(request: GenerationRequest):
    """Stream action workflow."""
    #input_prompt = {"prompt": request.prompt}
    input_prompt = request.prompt # list
    print(input_prompt)
    response = []

    async def event_stream():
        async for event in react_graph.async_astream_react_agent(input_prompt):
            if "messages" in event:
                # Serialize the last message
                serialized = dumpd(event["messages"][-1])
                yield f"data: {json.dumps(serialized)}\n\n" 

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# To run this server:
# Run in your terminal: uvicorn app:app --reload --host 0.0.0.0 --port 8050


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8050)

