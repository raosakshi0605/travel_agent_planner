# Personal Travel Planner Agent

## About

This project is a simple **Personal Travel Planner Agent** built using Google ADK.

The agent takes a user's travel requirements and creates a simple travel plan based on the destination, number of days, budget, and interests.

## Features

- Understands travel requirements
- Suggests places to visit
- Creates a day-wise itinerary
- Gives an estimated budget
- Checks whether the plan fits the user's budget
- Considers the user's interests

## Example Input

I want to visit Jaipur for 3 days with a budget of ₹15,000. I like history and local food.

## Files

- `agent.py` - Main travel planner agent
- `requirements.txt` - Required Python package
- `README.md` - Project information

## How to Run

First create and activate the virtual environment.

Then install the required package:

```bash
pip install -r requirements.txt

## Guardrails and Security

The Travel Planner Agent includes guardrails to keep the agent focused on
travel-related tasks and prevent it from responding to unrelated requests.

Security measures include:

- Restricting the agent to travel-related requests
- Protection against prompt injection attempts
- Preventing disclosure of system instructions
- Preventing disclosure of API keys, passwords, tokens, and credentials
- Rejecting unrelated requests such as coding, political, medical, or legal questions
- Keeping sensitive environment variables out of the repository

The guardrails were tested using multiple valid, invalid, prompt-injection,
and sensitive-data requests.
