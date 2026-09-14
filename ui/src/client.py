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
import json


logging.basicConfig(
    level=logging.DEBUG,  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

BASE_API_URL = "http://agent-app:8050"
TEXT_RESPONSE_URL= f"{BASE_API_URL}/generate-text"
INITIATE_WORKFLOW = f"{BASE_API_URL}/initiate-workflow"
RESUME_WORKFLOW = f"{BASE_API_URL}/resume-workflow"
INITIATE_WORKFLOW_STREAM = f"{BASE_API_URL}/initiate-workflow-stream"
RESUME_WORKFLOW_STREAM = f"{BASE_API_URL}/resume-workflow-stream"



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

        streaming_content = None  # accumulated tokens for the in-progress assistant bubble

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST",
                    INITIATE_WORKFLOW_STREAM,
                    json=formatted_prompt(messages),
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        ev = json.loads(line[len("data:"):].strip())
                        t = ev.get("type")

                        if t == "token":
                            if streaming_content is None:
                                streaming_content = ""
                                messages.append(ChatMessage(role="assistant", content=""))
                            streaming_content += ev["content"]
                            messages[-1] = ChatMessage(role="assistant", content=streaming_content)
                            yield messages, gr.update(visible=False), input_state, tool_state

                        elif t == "message":
                            # Boundary: close the current token bubble and surface any tool call.
                            streaming_content = None
                            m = ev["message"]
                            if "AIMessage" in m.get("id", []) and m["kwargs"].get("tool_calls"):
                                tc = m["kwargs"]["tool_calls"][0]
                                tool_state["tool_name"] = tc["name"]
                                messages.append(ChatMessage(
                                    role="assistant",
                                    content=f"Invoking with args {tc.get('args')}",
                                    metadata={"title": f"🛠️ Used tool {tc['name']}"}))
                                yield messages, gr.update(visible=False), input_state, tool_state

                        elif t == "interrupt":
                            streaming_content = None
                            tool_state["tool_name"] = ev["value"]["tool_call"]["name"]
                            messages.append(ChatMessage(
                                role="assistant",
                                content=f"{ev['value']['question']}",
                                metadata={"title": "🛠️ Interrupt triggered"}))
                            yield messages, gr.update(visible=True), input_state, tool_state

                        elif t == "error":
                            messages.append(ChatMessage(role="assistant", content=f"Error: {ev['detail']}"))
                            yield messages, gr.update(visible=False), input_state, tool_state

                        elif t == "done":
                            break

            except httpx.HTTPError as e:
                raise HTTPException(status_code=422, detail=str(e))


    
    async def handle_feedback(action, data, messages,input_state, tool_state):
        tool_request = tool_state.get("tool_name")
        input_prompt = input_state["input_prompt"]

        print("tool_request:",tool_request)

        # From Command to resume
        if action == "continue":
            resume_cmd = {"resume":{"action": "continue"},"config":config,"prompt":input_prompt}

        elif action == "update":
            arg_key = {"think_step": "thought", "tavily_search": "query"}.get(tool_request, "query")
            resume_cmd = {"resume":{"action": "update", "data": {arg_key:data}},"config":config,"prompt":input_prompt}

        elif action == "feedback":
            resume_cmd = {"resume":{"action": "feedback", "data": data},"config":config,"prompt":input_prompt}

        else:
            messages.append(ChatMessage(role="assistant", content="Invalid feedback option."))
            yield messages

        print(resume_cmd)

        if action:
            streaming_content = None  # accumulated tokens for the in-progress assistant bubble
            async with httpx.AsyncClient(timeout=None) as client:
                try:
                    async with client.stream(
                        "POST",
                        RESUME_WORKFLOW_STREAM,
                        json=resume_cmd,
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            ev = json.loads(line[len("data:"):].strip())
                            t = ev.get("type")

                            if t == "token":
                                if streaming_content is None:
                                    streaming_content = ""
                                    messages.append(ChatMessage(role="assistant", content=""))
                                streaming_content += ev["content"]
                                messages[-1] = ChatMessage(role="assistant", content=streaming_content)
                                yield messages, gr.update(visible=False)

                            elif t == "message":
                                streaming_content = None
                                m = ev["message"]
                                if "AIMessage" in m.get("id", []) and m["kwargs"].get("tool_calls"):
                                    tc = m["kwargs"]["tool_calls"][0]
                                    tool_state["tool_name"] = tc["name"]
                                    messages.append(ChatMessage(
                                        role="assistant",
                                        content=f"Invoking with args {tc.get('args')}",
                                        metadata={"title": f"🛠️ Used tool {tc['name']}"}))
                                    yield messages, gr.update(visible=False)

                            elif t == "interrupt":
                                streaming_content = None
                                tool_state["tool_name"] = ev["value"]["tool_call"]["name"]
                                messages.append(ChatMessage(
                                    role="assistant",
                                    content=f"{ev['value']['question']}",
                                    metadata={"title": "🛠️ Interrupt triggered"}))
                                yield messages, gr.update(visible=True)

                            elif t == "error":
                                messages.append(ChatMessage(role="assistant", content=f"Error: {ev['detail']}"))
                                yield messages, gr.update(visible=False)

                            elif t == "done":
                                break

                except httpx.HTTPError as e:
                    raise HTTPException(status_code=502, detail=str(e))

        # Handling normal conversation
        else:
            yield None,gr.update(visible=False)


    # Event wiring
    submit.click(agent_response, inputs=[input, chatbot,input_state,tool_state], outputs=[chatbot, feedback_ui,input_state,tool_state], concurrency_limit=1)
    resume_button.click(handle_feedback, inputs=[feedback_action, feedback_data, chatbot,input_state,tool_state], outputs=[chatbot,feedback_ui], concurrency_limit=1)
    clear.click(lambda: ([], "", gr.update(visible=False), {}), outputs=[chatbot,input,feedback_ui,tool_state])


# ensures the server listens on all interfaces, not just inside the container.
ui.launch(server_name="0.0.0.0", server_port=7860)