# Personal Agent ✨

## Overview

## Tools
### ▶ Tavily Search

### ▶ Think Tools

## Key Architecture ⚙
1. VLLM Server
2. FastAPI
3. Postgres
4. Gradio UI

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
1. Switch to your favourite model in docker-compose.yml file under "command" argument. Make sure to use the right tool_chat_template or your own customised version and store it in ./vllm_server/template. 
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
2. Customise the generation-config file in ./vllm_server/genration_config. Make sure to look up the model card by the LLM provider
 
