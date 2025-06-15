from langchain_openai import ChatOpenAI
from typing import Dict, Any, Annotated,Optional,List
import requests
import gc
import torch
from tool.tools import AVAILABLE_TOOLS
from langchain_core.runnables import RunnableConfig
import os

SERVED_MODEL_NAME = os.getenv("SERVED_MODEL_NAME")
vLLM_SERVER_URL = "http://vllm:8000/v1"

# for reasoning model
reasoning = {
    "effort": "medium",  # 'low', 'medium', or 'high'
    "summary": "auto",  # 'detailed', 'auto', or None
}

extra_body={"stop": ["<|eot_id|>"],
              "reasoning": {
                            "effort": "medium",  # 'low', 'medium', or 'high'
                            "summary": "auto",  # 'detailed', 'auto', or None
                            },
            "top_k":None
            }

llm = ChatOpenAI(
    model=SERVED_MODEL_NAME,
    openai_api_base=vLLM_SERVER_URL,
    openai_api_key="dummy-key",
    #temperature=0, # Set to 0 for more deterministic tool use
    # top_p= None,
    # max_tokens=150, # Control output length if needed
    extra_body=extra_body
)

llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS,tool_choice="auto")


async def async_generate_text_response(prompt:str | List,
                                  llm:Annotated[ChatOpenAI,"Must be ChatOpenAI class langchain wrapper"]=llm):

        return await llm.ainvoke(prompt)


async def async_generate_tool_response(prompt:str|List|Dict, config:RunnableConfig,
                                       llm_with_tools=llm_with_tools):
        

        return await llm_with_tools.ainvoke(prompt,config=config)

def check_server_status():
    try:
        response = requests.get("http://vllm:8000/health")
        if response.status_code == 200:
            print("vllm server is running")
            return True
    except requests.exceptions.ConnectionError:
        print("vllm server is not running")
        return False
    
def clear_memory():
     gc.collect()
     torch.cuda.empty_cache()
