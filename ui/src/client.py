import gradio as gr
from langgraph.types import Command, Interrupt
import httpx
from fastapi import HTTPException
from gradio import ChatMessage
from langchain_core.load import dumpd, dumps, load, loads
from langchain_core.runnables import RunnableConfig
import uuid
import logging
import sys


logging.basicConfig(
    level=logging.DEBUG,  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

BASE_API_URL = "http://agent-app:8050"
TEXT_RESPONSE_URL= f"{BASE_API_URL}/generate-text"
INITIATE_WORKFLOW = f"{BASE_API_URL}/initiate-workflow"
RESUME_WORKFLOW = f"{BASE_API_URL}/resume-workflow"



with gr.Blocks() as ui:
    gr.Markdown("# Personal Agent ✨")
    chatbot = gr.Chatbot(type="messages",label="Hi! I'm your personal agent. How can I help?")
    input = gr.Textbox(placeholder="Enter your message here",)
    submit = gr.Button("Submit")
    clear = gr.Button("Clear")
    
    tool_state = gr.State({})
    input_state = gr.State({})

    # Feedback UI (initially hidden)
    with gr.Row(visible=False) as feedback_ui:
        feedback_action = gr.Radio(choices=["continue", "update", "feedback"], label="Choose Action")
        feedback_data = gr.Textbox(label="Additonal Feedback/Comments (e.g., args or feedback)")
        resume_button = gr.Button("Submit Feedback")

    


    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    def formatted_prompt(messages:list, config:RunnableConfig=config):
        """extract user and prompt key value"""
        print(messages)
        formatted_prompt = {"prompt":[{"role":messages[-1].role,"content":messages[-1].content}],"config":config}

        return formatted_prompt


    async def agent_response(prompt, messages,input_state,tool_state):
        
        messages.append(ChatMessage(role="user", content=prompt))
        input_state["input_prompt"] = formatted_prompt(messages)["prompt"]

        yield messages, gr.update(visible=False), input_state,None 

        async with httpx.AsyncClient() as client:
            try:
                json_response = await client.post(
                    INITIATE_WORKFLOW,
                    json=formatted_prompt(messages),
                    timeout=60.0
                )
                json_response.raise_for_status()
    
            except httpx.HTTPError as e:
                raise HTTPException(status_code=422, detail=str(e))


        print("ori_json_response:", json_response.json())
        print("ori_response:", json_response.json()["response"])
        response = json_response.json()["response"]# deserialize to lc format
        print("response:", response)
        for chunk in response:
            
            if "AIMessage" in chunk["id"]:
                #if chunk["kwargs"]["content"]:
                messages.append(ChatMessage(role="assistant", content=chunk["kwargs"]["content"]))
                yield messages, gr.update(visible=False), input_state, None

                if chunk['kwargs']["tool_calls"]:
                    print("chunk:",chunk)
                    print("tool_state:",tool_state)
                    tool_state["tool_name"]= chunk['kwargs']["tool_calls"][0]["name"]
                    messages.append(ChatMessage(role="assistant", content=f"Invoking with args {tool_state["tool_name"]}",
                                  metadata={"title": f"🛠️ Used tool {chunk['kwargs']["tool_calls"][0]["name"]}"})) # 
                    
                    

                    yield messages, gr.update(visible=False), input_state, tool_state

                
                    
            
            elif "Interrupt" in chunk["id"]:
                print("chunk:",chunk)
                print("tool_state:",tool_state)
                tool_state["tool_name"] =  eval(chunk["repr"]).value["tool_call"]["name"]
                messages.append(ChatMessage(role="assistant",
                                            content=f"{eval(chunk["repr"]).value["question"]}",
                                            metadata={"title": f"🛠️ Interrupt triggered"}))
                    
                yield messages, gr.update(visible=True), input_state, tool_state


    
    async def handle_feedback(action, data, messages,input_state, tool_state):
        tool_request = tool_state["tool_name"] if tool_state["tool_name"] else None
        input_prompt = input_state["input_prompt"]

        print("tool_request:",tool_request)

        # From Command to resume
        if action == "continue":
            resume_cmd = {"resume":{"action": "continue"},"config":config,"prompt":input_prompt}

        elif action == "update":
            if tool_request == "think_step":
                args = "thought" 
            elif tool_request == "tavily_search":
                args = "query"
            resume_cmd = {"resume":{"action": "update", "data": {args:data}},"config":config,"prompt":input_prompt}

        elif action == "feedback":
            resume_cmd = {"resume":{"action": "feedback", "data": data},"config":config,"prompt":input_prompt}

        else:
            messages.append(ChatMessage(role="assistant", content="Invalid feedback option."))
            yield messages

        print(resume_cmd)
        
        if action:
            async with httpx.AsyncClient() as client:
                try:
                    json_response = await client.post(
                        RESUME_WORKFLOW,
                        json=resume_cmd,
                        timeout=60.0
                    )
                    json_response.raise_for_status()
                except Exception as e:
                    raise HTTPException(status_code=502, detail=str(e))

            print("ori_json_response:", json_response.json())
            print("ori_response:", json_response.json()["response"])
            response = json_response.json()["response"]# deserialize to lc format
            print("response:", response)
            for chunk in response:
            
                if "AIMessage" in chunk["id"]:
                    if chunk['kwargs']["tool_calls"]:
                        messages.append(ChatMessage(role="assistant", content=f"Invoking with args {chunk['kwargs']["tool_calls"][0]["name"]}",
                                    metadata={"title": f"🛠️ Used tool {chunk['kwargs']["tool_calls"][0]["name"]}"})) #  have to sort out no. of abnormal tool call returned'
                        
                        yield messages, gr.update(visible=False)

                    if chunk["kwargs"]["content"]:
                        messages.append(ChatMessage(role="assistant", content=chunk["kwargs"]["content"]))
                        #time.sleep(0.001)
                        yield messages, gr.update(visible=False)
        
        # Handling normal conversation
        else:
            yield None,gr.update(visible=False)


    # Event wiring
    submit.click(agent_response, inputs=[input, chatbot,input_state,tool_state], outputs=[chatbot, feedback_ui,input_state,tool_state], concurrency_limit=1)
    resume_button.click(handle_feedback, inputs=[feedback_action, feedback_data, chatbot,input_state,tool_state], outputs=[chatbot,feedback_ui], concurrency_limit=1)
    clear.click(lambda: ([],[],[],{}), outputs=[chatbot,input,feedback_ui,tool_state])


# ensures the server listens on all interfaces, not just inside the container.
ui.launch(server_name="0.0.0.0", server_port=7860)