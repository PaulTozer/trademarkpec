"""
Register the Trademark Classification container app as an OpenAPI tool
on a Foundry prompt agent.

This is the quickest way to use your deployed container app as an agent
in the new Microsoft Foundry portal.

Prerequisites:
  pip install azure-ai-projects azure-identity python-dotenv

Usage:
  python register_agent.py

Environment variables (set in .env or shell):
  AZURE_AI_PROJECT_ENDPOINT  – Your Foundry project endpoint
  AZURE_AI_MODEL             – Model deployment name (default: gpt-5.2-chat)
  CONTAINER_APP_URL          – Your deployed container app URL
                               (default: https://trademarkpec.proudwave-496cbcb3.swedencentral.azurecontainerapps.io)
"""

import os
import json
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT", os.getenv("AZURE_AI_ENDPOINT", ""))
MODEL = os.getenv("AZURE_AI_MODEL", "gpt-5.2-chat")
CONTAINER_APP_URL = os.getenv(
    "CONTAINER_APP_URL",
    "https://trademarkpec.proudwave-496cbcb3.swedencentral.azurecontainerapps.io",
)

AGENT_NAME = "TrademarkClassifier"
AGENT_INSTRUCTIONS = """You are an expert trademark classification assistant.

When a user provides a business website URL or describes their business, use the
classifyTrademarks tool to analyse the business and return relevant Nice
Classification trademark classes.

Present the results clearly, showing:
- Class number and name
- Confidence score
- Relevant specification terms

If the user provides a URL, pass it as the 'url' parameter.
If the user describes their business in text, pass it as the 'business_description' parameter.
"""

# ---------------------------------------------------------------------------
# Fetch the OpenAPI spec from the deployed container app
# ---------------------------------------------------------------------------
print(f"Fetching OpenAPI spec from {CONTAINER_APP_URL}/openapi.json ...")
resp = requests.get(f"{CONTAINER_APP_URL}/openapi.json", timeout=15)
resp.raise_for_status()
openapi_spec = resp.json()

# Update the server URL to point at the deployed container app
openapi_spec["servers"] = [{"url": CONTAINER_APP_URL}]

print("OpenAPI spec loaded successfully.")
print(f"  Title:      {openapi_spec['info']['title']}")
print(f"  Operations: {list(openapi_spec['paths'].keys())}")

# ---------------------------------------------------------------------------
# Create the OpenAPI tool definition
# ---------------------------------------------------------------------------
trademark_tool = {
    "type": "openapi",
    "openapi": {
        "name": "trademark_classifier",
        "description": "Analyses a business website or description and returns relevant Nice Classification trademark classes with specification terms and confidence scores.",
        "spec": openapi_spec,
        "auth": {
            "type": "anonymous",
        },
    },
}

# ---------------------------------------------------------------------------
# Connect to Foundry and create/update the agent
# ---------------------------------------------------------------------------
print(f"\nConnecting to Foundry project: {PROJECT_ENDPOINT}")

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as client,
):
    # Create a versioned agent with the OpenAPI tool
    agent = client.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=AGENT_INSTRUCTIONS,
            tools=[trademark_tool],
        ),
    )

    print(f"\n{'=' * 50}")
    print(f"  Agent created successfully!")
    print(f"  Name:    {AGENT_NAME}")
    print(f"  ID:      {agent.id}")
    print(f"  Model:   {MODEL}")
    print(f"{'=' * 50}")
    print(f"\nYou can now use this agent in the Microsoft Foundry portal.")
    print(f"Go to your project → Agents → {AGENT_NAME}")
    print(f"Or use the agent playground to test it.")
