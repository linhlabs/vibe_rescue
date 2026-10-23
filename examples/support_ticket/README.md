# Support Ticket Demo

A synthetic support-ticket workflow accepts a message, classifies its intent,
builds a tool plan and returns a small audit event. The example contains no
real customer data and makes no claim that its PII controls are sufficient.

## Request journey

1. `gateway.api.submit` receives the message and email address.
2. `domain.policy.classify_intent` labels the request.
3. `orchestrator.agent.build_plan` asks an allowed tool for a response.
4. `audit.events.redact_event` prepares an audit event without the email address.
5. `gateway.api.respond` returns a ticket result.

The TypeScript UI calls an HTTP endpoint, but the static Python graph does not
prove the UI-to-API binding. A reviewer must trace that route and test egress,
authorization, failure handling and audit storage on the actual application.
