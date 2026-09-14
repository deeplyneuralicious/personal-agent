from typing import Annotated, TypedDict, Dict, List,Any,Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt
import logging
import sys
import uuid
import asyncio

from llm.llm_services import llm_with_tools, async_generate_tool_response
from tool.tools import tool_node
from langgraph.checkpoint.memory import InMemorySaver

from dotenv import load_dotenv
from state import AgentState



load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

checkpointer = InMemorySaver()

# counter_call_llm = 0
# counter_human_node = 0

async def call_llm(state: AgentState, config:RunnableConfig) -> Dict[str, Any]:
    """Calls the LLM hosted in vLLM server."""
    print("--- Calling LLM ---")

    # global counter_call_llm

    # counter_call_llm += 1 # This code will run again on resuming!
    # print(f"Entered `call_llm` a total of {counter_call_llm} times")
    # print("state:",state['messages'])

    response = await async_generate_tool_response(state['messages'], config=config)# All the context
 

    return {"messages":[response]}


def call_human_feedback(state: AgentState) -> Command[Literal["call_llm", "tool_node"]]:
    """Request feedback from a human."""
    
    last_message = state["messages"][-1]
    tool_call = last_message.tool_calls[-1]

    # global counter_human_node
    # counter_human_node += 1 # This code will run again!
    # print(f"Entered human_node a total of {counter_human_node} times")
    human_review = interrupt(
        {
        "question": "Is this correct?",
        # Surface tool calls for review
        "tool_call": tool_call,
        }
    )
    
    review_action = human_review["action"]
    review_data = human_review.get("data")

    # if approved, call the tool
    if review_action=="continue":
        return Command(goto="tool_node")
    
    # update the AI message AND call tools (change some parameters)
    elif review_action == "update":
        updated_message = {
            "role":"ai",
            "content":last_message.content,
            "tool_calls":[
                {
                    "name":tool_call["name"],
                    "args":review_data, # edit tool_call arguement
                    "id":tool_call["id"],

                }
            ],
            "id":last_message.id
        }
        return Command(goto="tool_node" ,update={"messages": [updated_message]})# update the latest AI message(tool_call in this case). Then go to tool node so it can access updated tool call args in AI Message
    
    # provide feedback to LLM
    elif review_action == "feedback":

        tool_message = {
            "role":"tool",
            "content":review_data,
            "name": tool_call["name"],
            "tool_call_id":tool_call["id"]
        }
        return Command(goto="call_llm", update={"messages": [tool_message]}) # tool call message sent back to AI 
  


def routing_decision(state) -> Literal["END", "call_human_feedback"]:
    """Route LLM decision to either seeking human feedback or ending the graph """

    if len(state["messages"][-1].tool_calls) == 0:
        ("--- Decision: Latest message is AIMessage with content without tool calling, ending graph ---")
        return "END"
    else:
        print("--- Decision: tool_calls in state, proceeding to 'call_human_feedback' node ---")
        return "call_human_feedback"





# --- Build the Graph ---
class AgentWorkflow:
    def __init__(self):
        self.call_llm = call_llm
        self.tool_node = tool_node
        self.call_human_feeedback = call_human_feedback
        self.routing_decision = routing_decision
        self.agent_state = AgentState
        self.checkpointer = checkpointer

        self.workflow = StateGraph(self.agent_state)
        # Define the nodes
        self.workflow.add_node("call_llm", self.call_llm)
        self.workflow.add_node("tool_node", self.tool_node)
        self.workflow.add_node("call_human_feedback", self.call_human_feeedback)

        # Set the entry point
        self.workflow.set_entry_point("call_llm")

        self.workflow.add_conditional_edges(
            "call_llm", # From node 'llm'
            self.routing_decision, # Use this function to determine the next node
            {
                "END":END,
                "call_human_feedback":"call_human_feedback"
            }
        )

        # After calling a tool, return to the LLM to process the results (tool outputs)
        self.workflow.add_edge("tool_node", "call_llm")

        # Compile the graph
        self.react_graph = self.workflow.compile(checkpointer=self.checkpointer)

    async def async_predict_react_agent_answer(self,inputs):
        """Invoke Method"""

        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        messages = await self.react_graph.ainvoke({"messages": inputs}, config=config,stream_mode="debug")
        return {"response": messages[-1]}# return coroutine object, AI message + original message
    
        
    
    async def async_astream_react_agent(self,inputs,config:RunnableConfig):
        """Use this in initiate workflow API"""

        async for event in self.react_graph.astream({"messages":inputs}, config,stream_mode="values"): # use return will return coroutine instead of async generator
            if "messages" in event:
                yield event["messages"][-1] # async generator
            if '__interrupt__' in event:
                yield event['__interrupt__'][-1]

    async def async_astream_command(self,inputs,config:RunnableConfig):
        """Use this in resume workflow API"""

        async for event in self.react_graph.astream(inputs, config,stream_mode="values"): # use return will return coroutine instead of async generator
            if "messages" in event:
                yield event["messages"][-1] # async generator




react_graph= AgentWorkflow()






