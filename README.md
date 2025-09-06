<h3 align="center"><img src="docs/thinker.png" height="64"><br>SkyPilot Thinker</h3>

## A controlled interface to protect LLM access.
SkyPilot Thinker is the backend service that interfaces with Large Language Models (LLMs). It 
provides a controlled environment to manage LLM access, ensuring that requests are handled securely and efficiently. 
Thinker processes incoming requests from the Messenger service, interacts with the LLM API, and returns the generated 
responses.


# How to build and run Thinker
```bash
# build the container image as skypilot-thinker then run it
# 
docker build -t skypilot-thinker .
docker run --rm -p 8008:8008 --env-file conf/.env.local --network skypilot --name skypilot-thinker skypilot-thinker
```