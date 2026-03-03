# Architecture Map — Personal Execution Agent

> Auto-generated from GitNexus knowledge graph (7 files, 73 symbols, 11 execution flows)

---

## High-Level Overview

The codebase has two entry points: an **Agent** (multi-phase goal executor) and a **Chatbot** (conversational assistant). Both use OpenAI's API, but serve fundamentally different purposes.

```mermaid
graph TB
    subgraph Entry Points
        A[agent.py<br><b>main</b>]
        C[chatbot.py<br><b>chat</b>]
    end

    subgraph Agent Core
        AL[agent_loop]
        EI[extract_intent]
        CL[clarify]
        SP[show_plan]
        EX[execute]
        VR[verify]
        RT[retry]
        LS[llm_structured]
    end

    subgraph Structured Response Models
        IR[IntentResponse]
        ASR[AgentStepResponse]
        VRR[VerifyResponse]
    end

    subgraph Prompts — utils/prompt.py
        GIP[get_intent_prompt]
        GAP[get_agent_prompt]
        GVP[get_verify_prompt]
        GRP[get_retry_prompt]
        GSP[get_system_prompt]
    end

    subgraph Tools — utils/tools.py
        ET[execute_tool]
        GTD[get_tools_description]
        subgraph Tool Registry
            T1[add_task]
            T2[complete_task]
            T3[list_tasks]
            T4[create_note]
            T5[read_notes]
            T6[set_reminder]
            T7[list_reminders]
            T8[send_email]
            T9[ask_user]
            T10[get_time]
            T11[verify tool]
            T12[done]
        end
    end

    subgraph Memory — utils/memory.py
        BM[BaseMemory]
        SWM[SlidingWindowMemory]
        TBM[TokenBasedMemory]
        SM[SummaryMemory]
        SEL[select_memory]
    end

    subgraph Logging — utils/logging.py
        SL[save_log]
    end

    A --> AL
    AL --> EI --> LS
    AL --> CL --> LS
    AL --> SP
    AL --> EX --> LS
    AL --> VR --> LS
    AL --> RT --> LS

    LS --> IR
    LS --> ASR
    LS --> VRR

    EI --> GIP
    CL --> GIP
    EX --> GAP
    EX --> GTD
    EX --> ET
    VR --> GVP
    RT --> GRP
    RT --> GTD
    RT --> ET

    ET --> T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 & T9 & T10 & T11 & T12

    C --> SEL
    C --> SL
    C --> GSP
    SEL --> SWM & TBM & SM
    SWM --> BM
    TBM --> BM
    SM --> BM

    AL --> SL
```

---

## Functional Modules

| Module | Cohesion | Files | Purpose |
|--------|----------|-------|---------|
| **Agent Orchestration** | 81% | `agent.py`, `utils/prompt.py` | Core agent loop: intent extraction, clarification, planning, verification |
| **Execution & Retry** | 75% | `agent.py`, `utils/prompt.py`, `utils/tools.py` | Tool-based step execution and gap-fixing retry logic |
| **Read Tools** | 67% | `utils/tools.py` | Tools that read state: `list_tasks`, `read_notes`, `list_reminders`, `verify` |
| **Write Tools** | 67% | `utils/tools.py` | Tools that mutate state: `add_task`, `complete_task`, `create_note`, `set_reminder` |
| **Memory Strategies** | 92% | `utils/memory.py` | Pluggable memory backends for the chatbot |
| **Chat & Logging** | 86% | `chatbot.py`, `utils/memory.py`, `utils/logging.py` | Conversational chatbot with memory and log persistence |

---

## Execution Flows

### 1. Agent Goal Execution (primary flow)

```
main() → agent_loop() → 5 phases:

Phase 1: extract_intent()  → llm_structured(IntentResponse)  → get_intent_prompt()
Phase 2: clarify()         → llm_structured(IntentResponse)  → get_intent_prompt()
Phase 3: show_plan()       → (display only)
Phase 4: execute()         → llm_structured(AgentStepResponse) → execute_tool() loop
Phase 5: verify()          → llm_structured(VerifyResponse)  → get_verify_prompt()
     └── retry()           → llm_structured(AgentStepResponse) → execute_tool() loop
```

### 2. Chatbot Conversation

```
chat() → select_memory() → [SlidingWindowMemory | TokenBasedMemory | SummaryMemory]
       → OpenAI chat completions (free-form, no structured output)
       → save_log()
```

---

## File Map

```
.
├── agent.py                  # Agent entry point + orchestrator (5 phases)
│                              #   Models: IntentResponse, AgentStepResponse, VerifyResponse
│                              #   Core:   llm_structured(), agent_loop()
│
├── chatbot.py                # Chatbot entry point (conversational)
│
├── utils/
│   ├── prompt.py             # All system prompts (intent, agent, verify, retry)
│   ├── tools.py              # Tool registry + 12 tools + execute_tool()
│   ├── memory.py             # BaseMemory + 3 strategies + select_memory()
│   └── logging.py            # save_log() → JSON file persistence
│
├── data/                     # Runtime JSON storage (tasks, notes, reminders)
├── requirements.txt          # openai, pydantic, python-dotenv, tiktoken
└── .env                      # OPENAI_API_KEY
```

---

## Structured Output Models

All LLM calls in the agent use `client.beta.chat.completions.parse()` with Pydantic models:

| Model | Used By | Fields |
|-------|---------|--------|
| `IntentResponse` | `extract_intent`, `clarify` | `intent`, `needs_clarification`, `clarification_questions`, `sub_goals` |
| `AgentStepResponse` | `execute`, `retry` | `thought`, `action`, `input` |
| `VerifyResponse` | `verify` | `satisfied`, `summary`, `agent_gaps`, `human_next_steps` |
