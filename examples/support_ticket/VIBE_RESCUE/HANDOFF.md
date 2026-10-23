<!-- markdownlint-disable MD013 -->

# Team handoff — support_ticket

**Evidence packet, not a readiness verdict.** Open the architecture map, follow source anchors, then assign the probes below. No target tests or runtime traces were run by this command.

[Review worksheet](REVIEW_WORKSHEET.md) · [Architecture Atlas](architecture.html) · [Source Explorer](source-explorer.html) · [Machine JSON](architecture.json)

## Snapshot

- Git HEAD: `unknown`; tracked changes: `unknown`. Working-tree evidence is not a deployed-build identity.
- Atlas fingerprint: `dd33c0294b011e9e60f539b99a4200b7ad2d2feaed3dbffe901a8d5da0bf5f3b`; approved source areas: `.`.
- 6 code files; 6 blocks; 8 cross-block relations; documented journeys: 1; unbound steps: 0.

## Documented purpose

A synthetic support-ticket workflow accepts a message, classifies its intent, builds a tool plan and returns a small audit event. The example contains no real customer data and makes no claim that its PII controls are sufficient.

Source: [README.md:3](../README.md#L3)
**Documentation can be stale.**

## Next work for the team

- Trace UI/API and other cross-language edges; this Atlas inventories those files only. See [coverage](handoff.html#coverage).
- For each selected control, collect an exact-build runtime/fault receipt; names and tests are leads only. See [controls](handoff.html#controls).

## Functional blocks

### `actions` · Actions

The name is a control candidate, not proof of authorization enforcement. (source_docstring).
Source: [actions/tools.py:1](../actions/tools.py#L1).
1 files; 1 indexed Python functions. [Open block](architecture.html?block=actions).
Function leads: [actions.tools.allowed_tool](source-explorer.html?function=actions.tools.allowed_tool) [actions/tools.py:4](../actions/tools.py#L4).

### `audit` · Audit

A synthetic audit stub; storage and retention are outside this example. (source_docstring).
Source: [audit/events.py:1](../audit/events.py#L1).
1 files; 1 indexed Python functions. [Open block](architecture.html?block=audit).
Function leads: [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event) [audit/events.py:4](../audit/events.py#L4).

### `domain` · Domain

A placeholder classifier, not a production intent model. (source_docstring).
Source: [domain/policy.py:1](../domain/policy.py#L1).
1 files; 1 indexed Python functions. [Open block](architecture.html?block=domain).
Function leads: [domain.policy.classify_intent](source-explorer.html?function=domain.policy.classify_intent) [domain/policy.py:4](../domain/policy.py#L4).

### `gateway` · Gateway

Synthetic API boundary for the public handoff example. (source_docstring).
Source: [gateway/api.py:1](../gateway/api.py#L1).
1 files; 2 indexed Python functions. [Open block](architecture.html?block=gateway).
Function leads: [gateway.api.respond](source-explorer.html?function=gateway.api.respond) [gateway/api.py:15](../gateway/api.py#L15), [gateway.api.submit](source-explorer.html?function=gateway.api.submit) [gateway/api.py:8](../gateway/api.py#L8).

- → `audit` · import · 1 refs; [gateway/api.py:3](../gateway/api.py#L3) (exact_lexical).
- → `audit` · static_call · 1 refs; [gateway/api.py:11](../gateway/api.py#L11) (exact_lexical).
- → `domain` · import · 1 refs; [gateway/api.py:4](../gateway/api.py#L4) (exact_lexical).
- → `domain` · static_call · 1 refs; [gateway/api.py:9](../gateway/api.py#L9) (exact_lexical).
- → `orchestrator` · import · 1 refs; [gateway/api.py:5](../gateway/api.py#L5) (exact_lexical).

### `orchestrator` · Orchestrator

An intentionally small planning step; no model is called. (source_docstring).
Source: [orchestrator/agent.py:1](../orchestrator/agent.py#L1).
1 files; 1 indexed Python functions. [Open block](architecture.html?block=orchestrator).
Function leads: [orchestrator.agent.build_plan](source-explorer.html?function=orchestrator.agent.build_plan) [orchestrator/agent.py:6](../orchestrator/agent.py#L6).

- → `actions` · import · 1 refs; [orchestrator/agent.py:3](../orchestrator/agent.py#L3) (exact_lexical).
- → `actions` · static_call · 1 refs; [orchestrator/agent.py:7](../orchestrator/agent.py#L7) (exact_lexical).

### `web` · Web

No purpose statement located in approved documentation or module docstrings. (unknown).
1 files; 0 indexed Python functions. [Open block](architecture.html?block=web).

## Documented journeys

### Request journey

Source: [README.md:7](../README.md#L7).

1. `gateway.api.submit` receives the message and email address. — [gateway.api.submit](source-explorer.html?function=gateway.api.submit) [gateway/api.py:8](../gateway/api.py#L8); [README.md:9](../README.md#L9).
2. `domain.policy.classify_intent` labels the request. — [domain.policy.classify_intent](source-explorer.html?function=domain.policy.classify_intent) [domain/policy.py:4](../domain/policy.py#L4); [README.md:10](../README.md#L10).
3. `orchestrator.agent.build_plan` asks an allowed tool for a response. — [orchestrator.agent.build_plan](source-explorer.html?function=orchestrator.agent.build_plan) [orchestrator/agent.py:6](../orchestrator/agent.py#L6); [README.md:11](../README.md#L11).
4. `audit.events.redact_event` prepares an audit event without the email address. — [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event) [audit/events.py:4](../audit/events.py#L4); [README.md:12](../README.md#L12).
5. `gateway.api.respond` returns a ticket result. — [gateway.api.respond](source-explorer.html?function=gateway.api.respond) [gateway/api.py:15](../gateway/api.py#L15); [README.md:13](../README.md#L13).

## Harness and sensitive controls

**Candidate only. Runtime path unverified.**

### H01 · Intent and plan (agent)

Status: `source_candidate` (source_candidate); 2 candidate(s).

- source_candidate: [domain/policy.py:4](../domain/policy.py#L4) · [domain.policy.classify_intent](source-explorer.html?function=domain.policy.classify_intent)
- source_candidate: [orchestrator/agent.py:6](../orchestrator/agent.py#L6) · [orchestrator.agent.build_plan](source-explorer.html?function=orchestrator.agent.build_plan)

**Next proof:** Trace input → structured intent/plan, including ambiguous and failed planning cases.

### H02 · Tool authority and scope (agent)

Status: `source_candidate` (source_candidate); 1 candidate(s).

- source_candidate: [actions/tools.py:4](../actions/tools.py#L4) · [actions.tools.allowed_tool](source-explorer.html?function=actions.tools.allowed_tool)

**Next proof:** Prove each agent can call only approved tools and cannot escape its write scope.

### H03 · Timeout, cancel and termination (agent)

Status: `not_located_in_scope` (not_located_in_scope); 0 candidate(s).

- Not located in approved scope.

**Next proof:** Fault-inject timeout/cancel and prove a bounded terminal state with no orphan work.

### H04 · Retry and budget (agent)

Status: `not_located_in_scope` (not_located_in_scope); 0 candidate(s).

- Not located in approved scope.

**Next proof:** Measure retry/token/cost bounds and prove failures do not loop or silently continue.

### H05 · Evidence and final judge (agent)

Status: `not_located_in_scope` (not_located_in_scope); 0 candidate(s).

- Not located in approved scope.

**Next proof:** Trace a claim from source evidence through writer to the final audit verdict.

### H06 · Step audit trail (agent)

Status: `documented_only` (documented_only); 1 candidate(s).

- documented: [README.md:3](../README.md#L3)

**Next proof:** Check every decision and failure emits a redacted, ordered audit event.

### S01 · Swarm dispatch and concurrency (swarm)

Status: `not_located_in_scope` (not_located_in_scope); 0 candidate(s).

- Not located in approved scope.

**Next proof:** If parallel agents are intended, prove bounded fan-out, ordering and backpressure.

### S02 · Swarm independent review (swarm)

Status: `not_located_in_scope` (not_located_in_scope); 0 candidate(s).

- Not located in approved scope.

**Next proof:** Show a distinct reviewer, disagreement handling and no self-approval path.

### S03 · Swarm failure containment (swarm)

Status: `not_located_in_scope` (not_located_in_scope); 0 candidate(s).

- Not located in approved scope.

**Next proof:** Kill one worker mid-task; prove siblings, shared state and final response fail safely.

### P01 · Sensitive intake and classification (pii)

Status: `documented_only` (documented_only); 1 candidate(s).

- documented: [README.md:3](../README.md#L3)

**Next proof:** Identify entrypoints and data classes without copying real personal data into reports.

### P02 · Mask before provider egress (pii)

Status: `source_candidate` (source_candidate); 1 candidate(s).

- source_candidate: [audit/events.py:4](../audit/events.py#L4) · [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event)

**Next proof:** Fault-inject the masker at every outbound boundary and prove no raw identifier leaves.

### P03 · Storage, retention and consent (pii)

Status: `not_located_in_scope` (not_located_in_scope); 0 candidate(s).

- Not located in approved scope.

**Next proof:** Prove subject consent, isolation, deletion/TTL and storage policy with focused tests.

### P04 · Step and final audit redaction (pii)

Status: `source_candidate` (source_candidate); 1 candidate(s).

- source_candidate: [audit/events.py:4](../audit/events.py#L4) · [audit.events.redact_event](source-explorer.html?function=audit.events.redact_event)

**Next proof:** Inspect step/final audit and telemetry with synthetic identifiers; require zero raw leaks.

## Config, prompt and workflow paths

Path inventory only; the active loader and precedence are unverified.

## Coverage and unknowns

- 1 bounded docs read; 0 skipped; 0 Python parse errors; 1 non-Python files have file-level coverage.
- Documentation claims may be stale.
- Static calls/imports do not prove a runtime request path.
- Unique module-suffix bindings assume one indexed local module; dynamic sys.path can load another module.
- Function parameters/guards are indexed for Python only; other languages retain file-level blocks.
- Control candidates are not a security or production-readiness verdict.
