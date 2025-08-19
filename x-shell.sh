#!/bin/bash

# declare a service name variable
SERVICE_NAME=adx-ingester

# detect if docker is installed
if ! [ -x "$(command -v docker)" ]; then
    echo "Docker is not installed. Please install docker and try again."
    exit 1
fi

# detect if docker-compose is installed
if ! [ -x "$(command -v docker compose)" ]; then
    echo "Docker Compose is not installed. Please install docker-compose and try again."
    exit 1
fi

# detect if the container is running and start if not
if [ ! "$(docker ps -q -f name=${SERVICE_NAME})" ]; then
    # start the compose
    docker compose up -d
fi

# Shell into the running container (-t = interactive)
docker exec -it ${SERVICE_NAME} /bin/bash