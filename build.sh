#!/bin/bash

project_name="personal-agent-services"

app_image_name="agent-app:latest"
app_container_name="agent-app"

ui_image_name="gradio-ui:latest"
ui_container_name="gradio-ui"

vllm_server_image_name="vllm-server:latest"
vllm_server_container_name="vllm-server"

action=$1
hf_token=$2

# app
build_app_image () {
    echo "Building agent_app Docker image..."

    cd app

    docker build -t $app_image_name .

    cd ..
}

# start_app_container (){
#     build_app_image
#     echo "Starting agent_app Docker container..."
#     docker run -p 8050:8050 --gpus all --name $app_container_name $app_image_name
# }


# ui
build_ui_image () {
    echo "Building gradio Docker image..."

    cd ui

    docker build -t $ui_image_name .
    
    cd ..
}

# start_ui_container (){
#     build_ui_image
#     echo "Starting gradio Docker container..."
#     docker run -p 7860:7860 --name $ui_container_name $ui_image_name
# }


build_vllm_server_image (){
    echo "Building vllm Docker image..."

    cd vllm_server

    if [ -n "$hf_token" ]; then
        docker build --build-arg HF_TOKEN=$hf_token -t $vllm_server_image_name .
    else
        docker build -t $vllm_server_image_name .
    fi


    
    cd ..    
}


delete_image (){
    echo "Deleting Docker image..."
    docker rmi -f $app_image_name $ui_image_name $vllm_server_image_name
}

deploy_services(){
    
    build_vllm_server_image

    build_app_image
    
    build_ui_image
    
    docker compose -f ./docker-compose.yml -p $project_name up -d
}

stop_services(){
    docker compose -f ./docker-compose.yml -p $project_name down -v

    delete_image



}


# stop_container (){
#     echo "Stopping and removing container..."
#     docker stop $container_name
#     docker rm $container_name
#     delete_image
# }

case $action in
    start)
        deploy_services
        ;;
    stop)
        stop_services
        ;;
    *)
        echo "Unknown action: $action"
        exit 1
        ;;
esac

