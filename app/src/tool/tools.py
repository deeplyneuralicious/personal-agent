from typing import Optional, Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from typing import List, Dict, Any

import json
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)
from langchain_tavily import TavilySearch
from langgraph.prebuilt import InjectedState,ToolNode
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv
import llm.llm_services

from state import AgentState

load_dotenv()


class BasicToolNode:
    """A node that runs the tools requested in the last AIMessage."""

    def __init__(self, tools: list) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}

    async def __call__(self, inputs: dict):

        # Handle think_step
        if messages := inputs.get("messages", []):
            message = messages[-1]# AI message
            outputs=[]
            print("messages:",messages)
            # No parallel tool_call enabled. Sequential tool call
            if (tool_name:= message.tool_calls[0]["name"])=="think_step":
               formatted_messages = self._convert_state_messages_format(messages)
               #formatted_messages = ",".join(messages)
               print("----formated_messages----\n",formatted_messages)

               for tool_call in message.tool_calls:
                    formatted_messages.append({"role":"user","content":tool_call["args"]["properties"]["thought"]})# extract thought args
                    tool_call["args"]["thought"] = json.dumps(formatted_messages)
                    print("----tool_call thought----\n",formatted_messages)
                    tool_result =  await self.tools_by_name[tool_call["name"]].ainvoke(
                        tool_call["args"]
                    )
                    outputs.append(
                        ToolMessage(
                            content=json.dumps(tool_result),
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"],
                        )
                    )

            else:

                for tool_call in message.tool_calls:
                    tool_result =  await self.tools_by_name[tool_call["name"]].ainvoke(
                        tool_call["args"]
                    )
                    outputs.append(
                        ToolMessage(
                            content=json.dumps(tool_result),
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"],
                        )
                    )
                    
            return {"messages": outputs}
            
        else:
            raise ValueError("No message found in input")


    def _convert_state_messages_format(self,messages:List[BaseMessage]):
        """
        Converts a list of LangChain BaseMessage objects to a list of dictionaries
        """
        formatted_messages = []

        for msg in messages:
            if isinstance(msg, SystemMessage): # if provided one
                formatted_messages.append({"role":"system",
                                            "content":msg.content,
                                            "additional_kwargs":msg.additional_kwargs,
                                            "response_metadata":msg.response_metadata,
                                            "id":msg.id})
                
            elif isinstance(msg, HumanMessage):
                formatted_messages.append({"role":"user",
                                            "content":msg.content,
                                            "additional_kwargs":msg.additional_kwargs,
                                            "response_metadata":msg.response_metadata,
                                            "id":msg.id})
                
            elif isinstance(msg, AIMessage):
                formatted_messages.append({"role":"assistant",
                                            "content":msg.content,
                                            "additional_kwargs":msg.additional_kwargs,
                                            "response_metadata":msg.response_metadata,
                                            "id":msg.id,
                                            "tool_calls":msg.tool_calls})
            
            elif isinstance(msg, ToolMessage):
                formatted_messages.append({"role":"tool",
                                            "content":msg.content,
                                            "name":msg.name,
                                            "id":msg.id,
                                            "tool_call_id":msg.tool_call_id})
            
        return formatted_messages




# Define calculator tool
class CalculatorInput(BaseModel):
    expression: str = Field(description="The mathematical expression to evaluate.")

@tool("calculator", args_schema=CalculatorInput)
async def calculator(expression: str) -> float:
    """Evaluates a simple mathematical expression."""
    print(f"--- Executing calculator with expression: {expression} ---")
    try:
        # WARNING: Using eval() is dangerous in production code due to security risks.
        # Use a safer expression evaluator library in a real application (e.g., asteval, numexpr).
        result = eval(expression)
        print(f"--- Calculator result: {result} ---")
        return float(result)
    except Exception as e:
        print(f"--- Calculator error: {e} ---")
        # Return error message as string
        return f"Error evaluating expression: {e}"


# think tool
class ThinkStepInput(BaseModel):
    thought: str|Dict = Field(description="Thinking steps.")

@tool("think_step",args_schema=ThinkStepInput)
async def think_step(thought:str|Dict, config:RunnableConfig) -> Dict[str,Any]:
    """to add a step to stop and think about whether it has all the information it needs to move forward."""

    print(f"--- Thinking steps: ---")

    think_step_prompt = f'''
    ## Using the think tool

    You are in a reflection phase. Review the provided conversation history and the current thought from the main reasoning process. 
    Your goal is to refine this thought, verify information, or plan the next best action.

    Before taking any action or responding to the user after receiving tool results, use the think tool as a scratchpad to:
    - List the specific rules that apply to the current request
    - Check if all required information is collected
    - Verify that the planned action complies with all policies
    - Iterate over tool results for correctness

    ## Rules
    - Use the think tool generously to jot down thoughts and ideas.
    
    ## Thought (to think about): {thought}'''

    print("---think_step_prompt---:\n",think_step_prompt)
    response = await llm.llm_services.async_generate_text_response(think_step_prompt,config=config)
    print("---think_step_response---\n",response)

    return response.content

    
web_search_tool = TavilySearch(max_search=2)


# List of available tools
AVAILABLE_TOOLS = [think_step,web_search_tool]


# Prepare tools for the LLM prompt (OpenAI function calling like format to embed in prompt) for llama > 8b
def format_tools_for_llm(tools):
    """Formats tools into a list suitable for inclusion in the Llama 3 system message."""
    formatted_list = []
    for tool_obj in tools:
        parameters_schema = tool_obj.args_schema.model_json_schema()
        formatted_list.append({
            "type": "function",
            "function": {
                "name": tool_obj.name,
                "description": tool_obj.description,
                "parameters": parameters_schema # Includes 'type', 'properties', 'required'
            }
        })
    return formatted_list





tool_node = BasicToolNode(tools=AVAILABLE_TOOLS)

# to create list of tools for chat template
TOOLS_FOR_LLM = format_tools_for_llm(AVAILABLE_TOOLS)


