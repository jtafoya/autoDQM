# Project Overview
This repository is a proof of concept to develope an automatic DQM monitor. It is made out of few parts (training, application, report building, plot generating, monitoring) that integrate a full pipeline.

## Content & Tone Guidelines
- I hate your complacency. I want you to be clear without wanting to make me feel good/smart/correct. We'll have an objective interaction

## Coding Style
- Every code modification must be properly estudied, evaluated and debugged before applying it. Unnecesary bugs are completely untolerable and disappointing
- Every code change/addition must be succintly documented within the code and explained in the README
- Do not overcomplicate things. Many times the resources you need are already available, and you just need to either check carefully for e.g. a setup.sh file to source, similar working examples to base yourself on, or ask me to point you to these.

# Technology Stack
- There's a setup file available to load whatever dependency you could need

# Gotchas & Anti-Patterns
- Avoid hardcoding things directly into the code. It's preferable these are loaded from some sort of config or vars file
- Avoid ENTIRELY defining duplicates of function accross different files. Definitions should be as general as possible, and these should only have to be called whenever needed e.g. by the central pipeline script.

# Testing and Quality
New changes must:
1. Be fully supported by the dependencies loaded for this project
2. Work well when incorporated to the rest of the code in this project
