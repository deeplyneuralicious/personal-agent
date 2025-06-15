from typing import List, Annotated, TypedDict, Optional, Sequence
from langchain_core.messages import BaseMessage
from typing import Dict, Any
from langgraph.graph.message import add_messages


# Define the agent's state
class AgentState(TypedDict):
    # The list of messages in the conversation history
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # Optional: Tool calls detected in the latest AI message
    tool_calls: Optional[List[Dict[str, Any]]]
    # Optional: Results from executing tools
    tool_results: Optional[List[Dict[str, Any]]]