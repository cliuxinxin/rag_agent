# RAG Agent Copilot Instructions

## Architecture Overview
This is a LangGraph-based RAG (Retrieval-Augmented Generation) agent system with Vue 3 frontend and FastAPI backend. Core components:
- **Graphs** (`src/graphs/`): LangGraph workflows for chat, QA, reading, writing, PPT generation, skills
- **Nodes** (`src/nodes/`): Individual processing steps (supervisor, search, answer, etc.)
- **State** (`src/state.py`): `AgentState` TypedDict with annotated fields for message/document accumulation
- **Skills** (`skills/`): Dynamic tools with `SKILL.md` metadata and `scripts/` code
- **Storage** (`storage/`): FAISS vector indices and document storage

## Key Patterns
- **Supervisor-Worker Architecture**: Supervisor node routes to workers (searcher, answerer) in conditional edges
- **Annotated State Fields**: Use `Annotated[List[T], operator]` for accumulation (e.g., `add_messages`, `add_documents`)
- **Skill Creation**: Skills are JSON-defined with metadata and Python scripts; use `run_skill_script` tool
- **API Routes**: Backend routes (`backend/api/routes/`) call compiled graphs via `graph.stream()`
- **Frontend Integration**: Vue 3 SPA calls FastAPI endpoints with SSE for streaming responses

## Development Workflows
- **Local Development**: Backend `cd backend && python start_server.py`; Frontend `cd frontend && npm install && ./start.sh`
- **Docker Deployment**: `docker-compose up -d --build` (mounts `./storage` and `./logs`)
- **Testing API**: Use `backend/test_api.sh` for endpoint validation
- **Adding Features**: Create new graph in `src/graphs/`, nodes in `src/nodes/`, route in `backend/api/routes/`

## Code Conventions
- **Imports**: Add project root to `sys.path` for cross-module imports
- **Environment**: Load `.env` for API keys (DeepSeek, Tencent Hunyuan)
- **Error Handling**: Use try/except in skill scripts; validate inputs in nodes
- **Documentation**: Update `README_MIGRATION.md` for architectural changes
- **Dependencies**: Pin versions in `requirements.txt`; use `langgraph-checkpoint-sqlite` for persistence

## Common Pitfalls
- **State Mutations**: Always return new state dicts in nodes; don't modify in-place
- **Graph Compilation**: Call `workflow.compile()` after defining edges
- **CORS**: Backend allows `localhost:5173` (Vite dev) and `:80` (Nginx prod)
- **Vector Stores**: Use FAISS with Tencent embeddings; persist in `./storage`
- **Auth**: Config in `config.yaml` with hashed passwords; routes check authentication</content>
<parameter name="filePath">/Users/liuxinxin/Documents/GitHub/rag_agent/.github/copilot-instructions.md