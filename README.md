# The Architect

**Terraform for MCP agent workflows.** Define your agent's domain in Python, get models, schemas, MCP tools, pipelines, and HITL approval flows — generated and deployed in one command.

```
architect apply examples/aces/workflow.py

Generating models...     done
Generating schemas...    done  14 entities
Generating tools...      done  70 CRUD tools
Creating tables...       done
Updating state...        done  v1

  Applied successfully. Run `architect serve` to start.
```

## Why

Building an MCP-powered agent backend means writing the same boilerplate for every entity: SQLAlchemy models, Pydantic schemas, repository classes, MCP tool functions, status pipelines, approval gates. For ACES (a content engine with 14 entities), that was **thousands of lines** of repetitive code.

The Architect replaces that with **783 lines of declarative Python** that generates everything:

| What you write | What you get |
|---|---|
| `EntityDefinition("brand", fields=[...])` | Model + Schema + Repository + Serialize + 5 CRUD tools |
| `PipelineDefinition("content_piece", statuses=[...])` | `transition_content_piece_status` tool with validation |
| `ToolDefinition.custom("my.module")` | Your business logic registered alongside CRUD |
| `DispatcherDefinition("publish", handler="...")` | HITL approval flow → dispatcher execution |

## How it works

```
WorkflowDefinition (Python)
        │
        ▼
  architect apply
        │
        ├── Generates: models, schemas, repos, serialize, tools
        ├── Creates: PostgreSQL tables with FKs
        ├── Generates: pipeline transition tools
        ├── Generates: approval tools (approve/reject/list)
        └── Saves: state version in DB
        │
        ▼
  architect serve
        │
        ├── Loads workflows from state
        ├── Imports generated models
        ├── Registers CRUD + pipeline + custom tools
        ├── Wires dispatchers to approval flow
        └── Serves MCP endpoints per workflow
              │
              ├── /mcp/aces/  → 108 tools
              └── /mcp/asos/  →  31 tools
```

## Quickstart

```bash
# Clone and install
git clone https://github.com/gentleman-dots/the-architect.git
cd the-architect
uv sync

# Start Postgres (or use an existing one)
export ARCHITECT_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/architect"

# Apply the ACES content workflow
uv run architect apply examples/aces/workflow.py

# Start the server
uv run architect serve
# → http://localhost:8000/health
# → MCP endpoint: http://localhost:8000/mcp/aces/
```

### Connect from Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "aces": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp/aces/"
    }
  }
}
```

## Defining a workflow

```python
from architect.primitives import (
    EntityDefinition, FieldDef, PipelineDefinition,
    ToolDefinition, Transition, WorkflowDefinition,
)

lead = EntityDefinition(
    name="lead",
    fields=[
        FieldDef("name", str, required=True, max_length=255),
        FieldDef("email", str, email=True),
        FieldDef("score", int, default=0),
        FieldDef("status", LeadStatus, default=LeadStatus.NEW),
    ],
)

pipeline = PipelineDefinition(
    entity_name="lead",
    statuses=["new", "contacted", "converted"],
    transitions=[
        Transition("new", "contacted"),
        Transition("contacted", "converted", approval_required=True),
    ],
)

workflow = WorkflowDefinition(
    name="My CRM", slug="crm",
    entities=[lead],
    pipelines=[pipeline],
    tools=[ToolDefinition.crud("lead")],
)
```

One `architect apply` gives you:
- `create_lead`, `get_lead`, `list_leads`, `update_lead`, `delete_lead`
- `transition_lead_status` (validates transitions, creates approvals)
- `approve_approval`, `reject_approval`, `list_pending_approvals`
- PostgreSQL table with indexes and constraints

## CLI

| Command | Description |
|---|---|
| `architect init <name>` | Scaffold a new workflow directory |
| `architect plan <workflow.py>` | Preview changes without applying |
| `architect apply <workflow.py>` | Generate code + create tables + save state |
| `architect serve` | Start server with all applied workflows |
| `architect state` | Show deployed workflow versions |
| `architect destroy <slug>` | Remove a workflow and its tables |
| `architect apikey create` | Generate an API key for MCP auth |
| `architect credential set <k> <v>` | Store encrypted provider credentials |
| `architect budget set <slug> <limit>` | Set token budget for a workflow |

## Architecture

```
src/architect/
  primitives/     # FieldDef, EntityDefinition, WorkflowDefinition, PipelineDefinition
  generators/     # Jinja2 templates → models, schemas, tools, pipeline tools, approval tools
  runtime/        # FastAPI app factory, MCP mounting, dispatcher, pipeline engine
  modules/        # Built-in: state, approvals, api_keys, credentials, budgets, executions
  cli/            # Click commands: init, plan, apply, serve, state, destroy
  generated/      # Output per workflow slug (auto-generated, do not edit)

examples/
  aces/           # Content engine: 14 entities, 108 tools
  asos/           # Sales CRM: 5 entities, 31 tools
```

## Production workflows

### ACES — Autonomous Content Engine System

Content production OS. 14 entities covering the full loop: brand → persona → idea → brief → piece → script → asset → render → calendar → publish → analytics.

- 70 CRUD tools + 6 pipeline transitions + 3 approval tools + 29 custom tools
- Pipelines: content_idea, content_piece (with HITL gates), asset, render_job, calendar, calendar_slot
- Custom tools: context-fetchers for Claude reasoning, copy/script generation, carousel planning, Gemini image gen, Exa research, analytics

### ASOS — Autonomous Sales Operating System

Sales CRM. 5 entities: project → lead → interaction → campaign → outreach_task.

- 25 CRUD tools + 3 pipeline transitions + 3 approval tools
- Pipelines: lead (new → enriched → contacted → replied → converted), campaign, outreach_task
- Dispatchers: send_email (Resend), delete_lead (HITL-gated)

## Stack

- **Python 3.12** + uv
- **FastAPI** + FastMCP (Streamable HTTP)
- **SQLAlchemy** async + asyncpg + PostgreSQL
- **Jinja2** for code generation
- **Click** for CLI
- **Pydantic v2** for validation
- **Fernet** for credential encryption

## Tests

```bash
uv run pytest          # 364 tests
uv run ruff check .    # Lint
uv run mypy src/       # Type check
```

## Deploy

```bash
# Railway (recommended)
railway init
railway add --plugin postgresql
railway up

# Docker
docker build -t the-architect .
docker run -e ARCHITECT_DATABASE_URL=... -p 8000:8000 the-architect
```

## License

MIT
