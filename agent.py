import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from utils.prompt import get_intent_prompt, get_agent_prompt, get_verify_prompt, get_retry_prompt
from utils.tools import execute_tool, get_tools_description
from utils.logging import save_log

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LOG_FILE = "agent_log.json"
MAX_STEPS = 15
RETRY_STEPS = 7
WRAP_UP_AT = 2
MAX_RETRIES = 2


# ─── Structured Response Models ──────────────────────────────────

class IntentResponse(BaseModel):
    intent: str
    needs_clarification: bool
    clarification_questions: list[str]
    sub_goals: list[str]


class AgentStepResponse(BaseModel):
    thought: str
    action: str
    input: str = ""


class VerifyResponse(BaseModel):
    satisfied: bool
    summary: str
    agent_gaps: list[str]
    human_next_steps: list[str]


def llm_structured(messages, response_model):
    """Call the LLM and return a parsed Pydantic model."""
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=messages,
        response_format=response_model,
    )
    return response.choices[0].message.parsed


# ─── Phase 1: INTENT — What does the user actually want? ─────────

def extract_intent(goal):
    print(f"\n{'='*50}")
    print(f"  Phase 1: EXTRACT INTENT")
    print(f"{'='*50}")

    result = llm_structured([
        {"role": "system", "content": get_intent_prompt()},
        {"role": "user", "content": f"User's goal: {goal}"},
    ], IntentResponse)

    print(f"  Intent  : {result.intent}")
    print(f"  Needs clarification: {result.needs_clarification}")
    if result.sub_goals:
        for i, sg in enumerate(result.sub_goals, 1):
            print(f"  Sub-goal {i}: {sg}")

    return result


# ─── Phase 2: CLARIFY — Do we have enough info? ──────────────────

def clarify(intent_result):
    if not intent_result.needs_clarification:
        return intent_result

    print(f"\n{'='*50}")
    print(f"  Phase 2: CLARIFY")
    print(f"{'='*50}")

    answers = []

    for q in intent_result.clarification_questions:
        print(f"\n  Agent asks: {q}")
        answer = input("  Your answer: ").strip()
        answers.append({"question": q, "answer": answer})
        print(f"  Noted: {answer}")

    clarification_context = "\n".join(
        f"Q: {a['question']}\nA: {a['answer']}" for a in answers
    )

    refined = llm_structured([
        {"role": "system", "content": get_intent_prompt()},
        {"role": "user", "content": (
            f"Original goal: {intent_result.intent}\n\n"
            f"Clarification from user:\n{clarification_context}\n\n"
            "Now refine the intent and sub-goals based on this new information. "
            "Set needs_clarification to false."
        )},
    ], IntentResponse)

    print(f"\n  Refined intent: {refined.intent}")
    for i, sg in enumerate(refined.sub_goals, 1):
        print(f"  Sub-goal {i}: {sg}")

    return refined


# ─── Phase 3: PLAN — Break into sub-goals (already done above) ───

def show_plan(intent_result):
    print(f"\n{'='*50}")
    print(f"  Phase 3: PLAN")
    print(f"{'='*50}")
    print(f"  Intent: {intent_result.intent}")
    for i, sg in enumerate(intent_result.sub_goals, 1):
        print(f"  [{i}] {sg}")
    print()


# ─── Phase 4: EXECUTE — Run the tool loop against the plan ───────

def execute(intent_result):
    print(f"{'='*50}")
    print(f"  Phase 4: EXECUTE")
    print(f"{'='*50}\n")

    intent = intent_result.intent
    sub_goals = intent_result.sub_goals

    system_prompt = get_agent_prompt(get_tools_description(), intent, sub_goals)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Begin executing the plan. Start with sub-goal 1."},
    ]

    state = {"intent": intent, "sub_goals": sub_goals, "steps": [], "achieved": False}

    step = 0
    while not state["achieved"] and step < MAX_STEPS:
        step += 1
        remaining = MAX_STEPS - step

        if remaining == WRAP_UP_AT:
            messages.append({
                "role": "user",
                "content": (
                    f"[SYSTEM] You have {remaining} steps left. "
                    "Wrap up now — verify your work and use 'done'."
                ),
            })

        # ── THINK ──
        parsed = llm_structured(messages, AgentStepResponse)
        thought = parsed.thought
        action = parsed.action
        tool_input = parsed.input

        print(f"  Step {step}:")
        print(f"    Think   : {thought}")
        print(f"    Act     : {action}({tool_input})")

        # ── ACT ──
        result = execute_tool(action, tool_input)
        print(f"    Observe : {result}\n")

        # ── UPDATE STATE ──
        state["steps"].append({
            "step": step,
            "thought": thought,
            "action": action,
            "input": tool_input,
            "result": result,
        })

        if action == "done":
            state["achieved"] = True
        else:
            messages.append({"role": "assistant", "content": parsed.model_dump_json()})
            messages.append({"role": "user", "content": f"Observation: {result}"})

    return state


# ─── Phase 5: VERIFY — Did we satisfy the original intent? ───────

def verify(state):
    print(f"{'='*50}")
    print(f"  Phase 5: VERIFY")
    print(f"{'='*50}")

    steps_summary = "\n".join(
        f"  - {s['action']}({s['input']}) → {s['result']}" for s in state["steps"]
    )

    parsed = llm_structured([
        {"role": "system", "content": get_verify_prompt()},
        {"role": "user", "content": (
            f"Intent: {state['intent']}\n\n"
            f"Sub-goals: {json.dumps(state['sub_goals'])}\n\n"
            f"Actions taken:\n{steps_summary}"
        )},
    ], VerifyResponse)

    result = parsed.model_dump()

    # Override: no agent gaps = satisfied, regardless of what the LLM said
    if not result["agent_gaps"]:
        result["satisfied"] = True

    print(f"  Satisfied : {'Yes' if result['satisfied'] else 'No'}")
    print(f"  Summary   : {result['summary']}")

    if result["agent_gaps"]:
        for gap in result["agent_gaps"]:
            print(f"  Agent gap : {gap}")

    if result["human_next_steps"]:
        print()
        for s in result["human_next_steps"]:
            print(f"  Your turn : {s}")

    state["verification"] = result
    return state


# ─── Phase 4b: RETRY — Fix gaps found by verification ────────────

def retry(state):
    gaps = state["verification"]["agent_gaps"]
    intent = state["intent"]

    print(f"\n{'='*50}")
    print(f"  Phase 4b: RETRY — Fixing {len(gaps)} gap(s)")
    print(f"{'='*50}\n")

    for gap in gaps:
        print(f"  Gap: {gap}")
    print()

    system_prompt = get_retry_prompt(get_tools_description(), intent, gaps)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Fix the gaps now."},
    ]

    step = 0
    while step < RETRY_STEPS:
        step += 1
        remaining = RETRY_STEPS - step

        if remaining == 1:
            messages.append({
                "role": "user",
                "content": "[SYSTEM] 1 step left. Use 'done' now with a summary of what you fixed.",
            })

        parsed = llm_structured(messages, AgentStepResponse)
        thought = parsed.thought
        action = parsed.action
        tool_input = parsed.input

        print(f"  Retry step {step}:")
        print(f"    Think   : {thought}")
        print(f"    Act     : {action}({tool_input})")

        result = execute_tool(action, tool_input)
        print(f"    Observe : {result}\n")

        state["steps"].append({
            "step": f"retry-{step}",
            "thought": thought,
            "action": action,
            "input": tool_input,
            "result": result,
        })

        if action == "done":
            break
        else:
            messages.append({"role": "assistant", "content": parsed.model_dump_json()})
            messages.append({"role": "user", "content": f"Observation: {result}"})

    return state


# ─── Orchestrator — Ties all 5 phases together ───────────────────

def agent_loop(goal):
    # Phase 1: Intent
    intent_result = extract_intent(goal)

    # Phase 2: Clarify
    intent_result = clarify(intent_result)

    # Phase 3: Plan
    show_plan(intent_result)

    # Phase 4: Execute
    state = execute(intent_result)

    # Phase 5: Verify → Retry loop (only retries on agent gaps, not human actions)
    for attempt in range(1, MAX_RETRIES + 1):
        state = verify(state)

        if state["verification"]["satisfied"]:
            break

        agent_gaps = state["verification"].get("agent_gaps", [])
        if agent_gaps and attempt < MAX_RETRIES + 1:
            state = retry(state)
        else:
            break

    # Final output
    print(f"\n{'='*50}")
    if state["verification"]["satisfied"]:
        print("  DONE — Agent completed all it can do. The rest is on you.")
    else:
        print("  PARTIAL — Some agent gaps remain after retries.")
    print(f"{'='*50}\n")

    save_log(LOG_FILE, {
        "goal": goal,
        "intent": state["intent"],
        "sub_goals": state["sub_goals"],
        "steps": state["steps"],
        "verification": state["verification"],
    })

    return state


# ─── Entry Point ──────────────────────────────────────────────────

def main():
    print("\n=== Personal Execution Agent ===")
    print("Intent → Clarify → Plan → Execute → Verify")
    print("Type 'quit' to exit.\n")

    while True:
        goal = input("Enter a goal: ").strip()
        if not goal:
            continue
        if goal.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        try:
            agent_loop(goal)
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
