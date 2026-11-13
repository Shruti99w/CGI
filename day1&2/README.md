# Hands-on Labs: From Prompts to Agents and Reliable Structured Outputs

Two modules, built around two business use cases:

| Module | Topic | Use case | Exercise |
|---|---|---|---|
| 1 | From Prompts to Agents | Internal knowledge assistant | Map three tasks to a prompt, a workflow or an agent |
| 2 | Reliable Prompting and Structured Outputs | Field extraction from support tickets | Build an extractor that returns validated JSON and retries on schema failure |

The code is small and follows production practice: config from the environment, one shared client with timeouts and retries, logging, typed data contracts, bounded loops, error handling, and offline tests.

---

## 0. Setup (10 minutes)

**You need:** VS Code with the Python extension, [uv](https://docs.astral.sh/uv/), and an OpenAI API key.

```bash
# 1. Open this folder in VS Code, then open a terminal (Ctrl + `)
uv sync                      # creates .venv and installs dependencies (incl. pytest)

# 2. Create your .env from the template
#    Windows PowerShell:  Copy-Item .env.example .env
#    Mac/Linux:           cp .env.example .env
#    Then open .env and paste your key after OPENAI_API_KEY=

# 3. Check everything works without spending tokens
uv run pytest tests/test_extractor.py -v      # 9 tests should pass

# 4. Check your API key works
uv run python -m module1.step1_llm_basics
```

**Always run scripts from the project root with `python -m`**, for example `uv run python -m module2.step3_json_schema`. That way the `common` package can be imported. The included `.vscode/settings.json` also sets `PYTHONPATH`, so VS Code's ▶ Run button works after you reopen the terminal.

Set `LOG_LEVEL=DEBUG` in `.env` to log the latency and token usage of every API call.

### Project layout

```
common/             shared, reusable production code
  config.py           settings from .env
  llm.py              OpenAI client wrapper: timeout, retries, usage logging
  structured.py       JSON Schema from Pydantic + validate + retry loop
  fake_client.py      scripted fake model for offline tests and demos
module1/            From Prompts to Agents
  data/kb/            4 company policy documents (the knowledge base)
  kb.py               search + read over the knowledge base
  step1..step5        guided steps
  exercise_task_mapping.py
module2/            Reliable Prompting and Structured Outputs
  data/tickets.jsonl  8 sample support tickets (incl. Hinglish, prompt injection, vague)
  schemas.py          TicketFields data contract with validators
  grounding.py        removes values not found in the ticket
  extractor.py        reference extractor (solution)
  run_extractor.py    batch CLI -> out/results.jsonl, out/failures.jsonl
  step1..step5        guided steps
  exercise_starter.py
tests/              offline tests (no API key needed)
```

---

## Module 1: From Prompts to Agents

**Use case:** an internal knowledge assistant that answers employee questions from company policies (leave, travel, expenses, IT access).

### Step 1. What an LLM does: the prompt-to-completion cycle
```bash
uv run python -m module1.step1_llm_basics
```
Observe:
- A request is a list of `messages` (system, user, assistant). The response is a completion, token `usage` and a `finish_reason`.
- At `temperature=0` the three names are (nearly) identical. At `1.2` they vary. The model samples the next token from a probability distribution.
- With `max_completion_tokens=25` the answer is cut off and `finish_reason` is `length`. Production code must check this.
- The model is **stateless**: it can't recall your team unless you send the history again.

### Step 2. Prompt vs fixed workflow vs agent
```bash
uv run python -m module1.step2_prompt_workflow_agent
```
The same two questions are answered three ways. Compare correctness, number of LLM calls and time.

| | Prompt | Workflow | Agent |
|---|---|---|---|
| Who decides the steps | nobody (one call) | your code | the model |
| Company knowledge | no | yes (retrieved) | yes (it searches) |
| Predictability | high | high | lower |
| Cost / latency | lowest | low | highest |
| Best for | single-step tasks | known, repeatable steps | open-ended, multi-lookup goals |

Discuss: the prompt-only answer sounds confident, but is it Acme's policy?

### Step 3. The agent loop: goal, plan, act, observe
```bash
uv run python -m module1.step3_agent_loop
uv run python -m module1.step3_agent_loop "How do I get production database access?"
```
Read `run_agent()` in [module1/step3_agent_loop.py](module1/step3_agent_loop.py). The loop is about 30 lines:

```
GOAL (user question)
 └─> LLM decides: PLAN + tool call(s)  ──> ACT: code runs the tool
        ^                                        |
        └──────────── OBSERVE: tool result <─────┘
     ... until the LLM answers without a tool call, or max_steps is reached
```
Production guardrails to point out: `max_steps`, tool errors returned to the model as data, defensive JSON parsing of tool arguments, step logging. The second default question (pets) is **not** in the knowledge base. Check that the agent says so instead of inventing a policy.

### Step 4. Model families and selection
```bash
uv run python -m module1.step4_model_selection
```
Compares the models in `OPENAI_COMPARE_MODELS` on a simple task and a reasoning task (latency, tokens, answer). Rule of thumb: **start with the smallest model that passes your test cases**, and move up only where quality fails. Family overview and a selection checklist are in the file's docstring.

### Step 5. When not to use an agent
```bash
uv run python -m module1.step5_when_not_to_use_agent
```
- **Part A, deterministic:** leave pro-rating and per-diem checks are a few lines of Python. They are free, instant, testable and always correct. No LLM.
- **Part B, high-risk:** the LLM only *proposes* an action as structured JSON. Code checks it against a policy (`auto` / `approval` / `blocked`), a human approves the risky one at the terminal, and every decision goes to `out/audit.log`.

### Exercise 1. Map three tasks to a prompt, a workflow or an agent (20 minutes)
1. Open [module1/exercise_task_mapping.py](module1/exercise_task_mapping.py) and read tasks T1 to T3.
2. Fill in `STUDENT_ANSWERS` with a choice and a justification that uses the decision criteria (`RUBRIC`).
3. Run `uv run python -m module1.exercise_task_mapping`. An LLM reviewer maps the same tasks and you compare.
4. For every disagreement, write one sentence on whose argument is stronger and why.

Stretch: add a T4 that should *not* use an LLM at all, and justify it.

---

## Module 2: Reliable Prompting and Structured Outputs

**Use case:** turn free-text support tickets into clean fields (name, email, order id, product, category, priority, sentiment, summary) that a CRM or routing system can trust.

### Step 1. Instruction structure, system prompts and few-shot examples
```bash
uv run python -m module2.step1_prompt_structure
```
Compare VAGUE, STRUCTURED and FEW-SHOT. A good system prompt has: **role, task, labels, rules, output format, and delimiters** (`<ticket>...</ticket>`) that separate instructions from data. Few-shot examples are sent as earlier user/assistant turns. They calibrate edge cases but cost tokens on every call.

### Step 2. Chain-of-thought and step-back prompting
```bash
uv run python -m module2.step2_reasoning_prompts
```
A refund case where "45 days > 30 days" is a trap: the item is defective, so the warranty applies.
- **CoT:** reason step by step, then a machine-readable `FINAL:` line. The app parses only that line and never shows the reasoning to the customer.
- **Step-back:** first ask for the general decision rules, then apply them to the case.
- With reasoning models you usually skip "think step by step". They reason internally.

### Step 3. Structured output with JSON Schema
```bash
uv run python -m module2.step3_json_schema
```
| Level | Guarantees | Risk |
|---|---|---|
| A. "Return JSON" in prompt | nothing | prose, ```` ``` ```` fences, parse errors |
| B. `json_object` mode | valid JSON syntax | wrong or missing keys |
| C. Strict `json_schema` | your exact keys, types and enums | still no business rules |

The schema is **generated from the Pydantic model** in [module2/schemas.py](module2/schemas.py) by `to_strict_schema()`. There's one source of truth for the API, validation and your code.

### Step 4. Parsing, validation and retries
```bash
uv run python -m module2.step4_validate_and_retry --offline   # no API key needed
uv run python -m module2.step4_validate_and_retry
```
Read `call_structured()` in [common/structured.py](common/structured.py). On a parse or validation error, the **exact error messages** are sent back to the model, which repairs its output. Retries are bounded (`max_attempts`). After that, raise and route to human review. Also handled: refusals (don't retry) and `finish_reason == "length"`.

Two kinds of retry, don't confuse them:
- **Transport retries** (429, 5xx, timeouts): done by the OpenAI SDK (`OPENAI_MAX_RETRIES`).
- **Content retries** (invalid output): done by our loop with error feedback.

### Step 5. Reducing unsupported or fabricated output
```bash
uv run python -m module2.step5_grounding
```
The NAIVE schema forces every field to be a string, so the model has to fill gaps. The GROUNDED extractor applies five defences:
1. Nullable fields: `str | None` makes "unknown" a valid answer.
2. Explicit rule: "never guess names, emails or order ids".
3. The ticket is wrapped in delimiters and treated as untrusted data (prompt-injection defence).
4. Verbatim evidence quotes for each identifier.
5. A **code check** ([module2/grounding.py](module2/grounding.py)) that removes any value or quote not found in the ticket.

### Exercise 2. Build a structured extractor that returns validated JSON and retries on schema failure (45 minutes)
1. Open [module2/exercise_starter.py](module2/exercise_starter.py) and complete TODO 1 to 7.
2. Check your work offline: `uv run pytest tests/test_exercise.py -v` (5 tests).
3. Run it on real tickets: `uv run python -m module2.exercise_starter`
4. Compare with the reference pipeline:
   ```bash
   uv run python -m module2.run_extractor
   ```
   Open `out/results.jsonl` and `out/failures.jsonl`. Check TCK-1007 (prompt injection) and TCK-1008 (vague).

Stretch goals:
- Add a `refund_requested: bool` field and a validator that requires `category == "billing"` or `"product_issue"` when it's true (`@model_validator`).
- Add a `language` field and check that TCK-1005 (Hinglish) still gets an English summary.
- Make `run_extractor` skip tickets already in `out/results.jsonl` so a re-run only processes new ones.
- Write a test in `tests/` for your new validator using `FakeClient`.

---

## Production checklist (what this lab demonstrates)
- [x] Secrets in `.env`, never in code; `.env` is git-ignored
- [x] One client with timeout and SDK retries; every call logs latency, tokens and finish reason
- [x] Pydantic models as data contracts; JSON Schema generated, not hand-written
- [x] Business-rule validation with bounded, error-informed retries
- [x] Grounding checks; nulls over guesses; untrusted input in delimiters
- [x] Agents with step limits, tool-error handling and traceable logs
- [x] Deterministic logic in code; high-risk actions behind approval and an audit log
- [x] Batch jobs that record failures instead of crashing; prompt version logged with results
- [x] Offline tests with an injectable fake client

## Troubleshooting
| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'common'` | Run from the project root with `uv run python -m module1.step1_llm_basics`, not `python module1/step1...py` |
| `OPENAI_API_KEY is missing` | Create `.env` from `.env.example` and add your key |
| `401 Incorrect API key` | Check the key has no quotes or spaces in `.env` |
| `429 rate limit / insufficient_quota` | Add billing credit, or wait and re-run (the SDK already retries) |
| `model not found` in step 4 | Remove that model from `OPENAI_COMPARE_MODELS` |
| `temperature not supported` | You set a reasoning model as `OPENAI_MODEL`; use `gpt-4o-mini` for these labs |
