# ELEC-498-AI-Assistant

AI coding Assistant for finding and fixing defects

Instructions for running:

Clone repository to your local machine

Open docker desktop and ensure docker engine is running

In the terminal run:

cd "C:\Users\your-path-to-repo\ELEC-498-AI-Assistant"

docker build -t elec-498-ai-assistant:latest .

docker run --rm elec-498-ai-assistant:latest

# How to use Pinecone/Open AI embedding

in .env file (should be in base directory) put three variables for APIs:

- OPENAI_API_KEY
- PINECONE_API_KEY
- BUG_IDS

BUG_IDS are used to select which bugs are used for each project (e.g., BUG_IDS=1,2,3 will be the first 3 bugs from 17 projects giving 3x17=51 bugs/fix pairs)
