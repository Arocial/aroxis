# LLM-Based Agent Framework and System

## Goals
Build AI agents that improve work efficiency (for me as software engineer).

## Core Concepts
### Agent Patterns
Agent Patterns are reusable templates for creating AI agents with specific behaviors and capabilities. They provide a structured way to define how agents should interact with users, tools, and other agents. Examples include `ChatAgent` for conversational interactions and `LLMBaseAgent` as the foundation for all agent types.

### Composed Agents
Composed Agents are specialized agents built by combining multiple Agent Patterns and tools. They are designed to handle complex workflows, such as code generation (`CoderComposer`). These agents leverage the flexibility of the framework to perform specific tasks efficiently.

### Tools
Tools are exteral components that are provided for LLM to extend it's capabilities.

### Commands
Commands are predefined actions that agents can execute, often triggered by user input. They provide a way for human to interact with agents. Commands may use tools as backend, since human and LLM could have similar use cases (e.g. Run a local command) as partners.
