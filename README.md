# Personal Agent ✨

## Overview 🔎
A fully containerized, modular, and asynchronous personal agent powered by an LLM backend. Built using LangGraph, FastAPI, Gradio, PostgreSQL, and vLLM, this project serves as a multi-tool, state-aware AI assistant. It supports dynamic tool-calling powered by Tavily API web search and additional think step tool.

## Architecture Overviews as Microservices 📦
```
+-------------------+
|    Gradio UI      |
|  (User Interface) |
+---------+---------+
          |^
          v|
+-----------------------+
|  FastAPI Main App     |
|  - Async LangGraph    |
|  - Tool Management    |
+----+------------+-----+
     |^           |^
     v|           v|
+--------+   +------------+
| vLLM   |   | PostgreSQL |
| Server |   |            |
+--------+   +------------+

```

## Key Components and Framework ⚙
1. **vLLM Server** as fast serving inference engine
2. Asynchronous **FastAPI** Backend with modular endpoints
3. **Postgres** for persistent chat and response storage
4. **Gradio UI** for chat interface
5. **LangGraph** Orchestration for graph-based, memory-aware stateful workflows
6. **Docker** to deploy containers as microservices

## Tools 🛠️ 
### ▶ Tavily Search
["Tavily"](https://www.tavily.com/)Fetches relevant real-time data from the web to enhance the LLM’s responses with current context.
### ▶ Think Tool
Inspired by ["Anthropic’s Claude Think Tool"](https://www.anthropic.com/engineering/claude-think-tool), a thinking step is created as tool whenever LLM decides to use it as part of a steps to aid reaching its final response. Essentially, the idea behind it is adding a step to stop and think about whether it has all the information it needs to proceed. This is particularly helpful when performing long chains of tool calls or in long multi-step conversations with the user.


## Getting Started 📌
1. Clone the repository.
```
git clone https://github.com/deeplyneuralicious/personal-agent
cd personal-agent
```
2. Include your TAVILY_API_KEY and HF_TOKEN in .env file in ./app/src/.env
3. Provide access to run the build.sh script.
```
chmod +x build.sh
```
4. Run the build.sh script. Wait for the docker containers finished building.
```
./build.sh start
```
5. Access the Gradio user interface via http://localhost:7860

## Additional Configurations
1. Switch to your favourite model in docker-compose.yml file under "command" argument. Make sure to use the right tool_chat_template or your own customised version and store it in vllm_server/template. 
```
      --model RedHatAI/Llama-3.2-1B-Instruct-FP8
      --served-model-name Llama-3.2-1B-Instruct-FP8
      --max-model-len 4096
      --gpu-memory-utilization 0.9
      --generation-config generation_config
      --enable-auto-tool-choice
      --tool-call-parser llama3_json
      --chat-template template/tool_chat_template_llama3.2_json.jinja
``` 
2. Customise the generation-config file in vllm_server/genration_config. Make sure to look up the model card by the LLM provider.
 
