# Summarization Feature Implementation Tickets

## Overview
These tickets implement a `call_tool_summarized` feature that reduces token usage by summarizing large tool outputs using LiteLLM.

## Token Savings
| Before | After | Savings |
|--------|-------|---------|
| Full tool output (5000+ tokens) | Summarized output (500-1000 tokens) | **80-90%** |

## Implementation Order

```
TICKET-001 ──► TICKET-004 ──► TICKET-002 ──► TICKET-003 ──► TICKET-005
    │              │              │              │              │
    ▼              ▼              ▼              ▼              ▼
  Service       Exports         Tool          Config         Tests
```

### Phase 1: Core Implementation (Required)
| Ticket | Title | Effort | Assignee |
|--------|-------|--------|----------|
| [TICKET-001](./TICKET-001-summarization-service.md) | Create Summarization Service | 4-6 hrs | |
| [TICKET-004](./TICKET-004-update-services-init.md) | Export from Services Package | 30 min | |
| [TICKET-002](./TICKET-002-call-tool-summarized.md) | Add call_tool_summarized Tool | 3-4 hrs | |

### Phase 2: Enhancement (Recommended)
| Ticket | Title | Effort | Assignee |
|--------|-------|--------|----------|
| [TICKET-003](./TICKET-003-summarization-config.md) | Add Configuration Settings | 1-2 hrs | |

### Phase 3: Quality (Required before Production)
| Ticket | Title | Effort | Assignee |
|--------|-------|--------|----------|
| [TICKET-005](./TICKET-005-integration-tests.md) | Add Integration Tests | 3-4 hrs | |

## Total Estimated Effort
- **Minimum viable**: 8-10 hours (Phase 1)
- **Full implementation**: 12-16 hours (All phases)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP Client (Claude Agent)                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ MCP Protocol
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Toolbox FastMCP Server                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                       MCP Tools                              │    │
│  │  ┌──────────────┐  ┌─────────────────────┐  ┌────────────┐  │    │
│  │  │  find_tools  │  │ call_tool_summarized│  │ call_tool  │  │    │
│  │  └──────────────┘  └─────────────────────┘  └────────────┘  │    │
│  │                              │                               │    │
│  │                              ▼                               │    │
│  │                    ┌─────────────────┐                       │    │
│  │                    │ Summarization   │◄── TICKET-001         │    │
│  │                    │    Service      │                       │    │
│  │                    └─────────────────┘                       │    │
│  │                              │                               │    │
│  └──────────────────────────────┼───────────────────────────────┘    │
│                                 │                                    │
│                                 ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      Tool Executor                           │    │
│  │  Executes tools via: HTTP, MCP, LiteLLM, Command Line        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LiteLLM Proxy                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │  Tool Execution │  │  Summarization  │  │    Chat API     │      │
│  │  (MCP REST)     │  │  (Chat API)     │  │                 │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Backend MCP Servers (Pods)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Internal │  │ Internal │  │   K8s    │  │   ...    │             │
│  │   Docs   │  │  Tools   │  │   Ops    │  │          │             │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow for call_tool_summarized

```
1. Agent calls call_tool_summarized(tool_name, args, max_tokens=2000)
                          │
                          ▼
2. Toolbox looks up tool in registry
                          │
                          ▼
3. ToolExecutor executes the tool (via LiteLLM/MCP/HTTP)
                          │
                          ▼
4. Raw output returned (possibly large)
                          │
                          ▼
5. SummarizationService.summarize_if_needed()
        │
        ├──► estimate_tokens(output)
        │           │
        │           ▼
        │    Is tokens > max_tokens?
        │           │
        │    NO ────┴──── YES
        │    │             │
        │    ▼             ▼
        │  Return       Call LiteLLM
        │  original     /v1/chat/completions
        │                   │
        │                   ▼
        │              Return summary
        │                   │
        └───────────────────┘
                          │
                          ▼
6. Return response with was_summarized flag
```

---

## Files Changed Summary

| File | Change Type | Ticket |
|------|-------------|--------|
| `app/services/summarization.py` | Create | TICKET-001 |
| `app/services/__init__.py` | Modify | TICKET-004 |
| `app/mcp_fastmcp_server.py` | Modify | TICKET-002 |
| `app/config.py` | Modify | TICKET-003 |
| `tests/test_summarization_integration.py` | Create | TICKET-005 |

---

## Definition of Done

- [ ] All tickets completed
- [ ] All tests passing (`pytest tests/`)
- [ ] Code reviewed
- [ ] Deployed to staging environment
- [ ] Tested with real MCP tools
- [ ] Documentation updated

## Questions?

Contact: [Your Team Lead]
