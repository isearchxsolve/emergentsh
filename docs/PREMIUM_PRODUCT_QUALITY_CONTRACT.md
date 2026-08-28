# Premium product E2E quality contract

Every EmergentSH application generated from a customer prompt is held to one default
release gate. The customer does not have to supply an exhaustive product requirements
document. The Planner must perform product discovery and record a business vision,
primary user journeys, success metrics, actors/permissions, and scope boundary.

The pipeline emits `QUALITY_GATE.json` only after all three verticals pass:

1. **Premium UI** — complete design tokens, responsive 390px+ behavior, Green
   Lantern-inspired emerald luminous glass depth, applied palette, interaction/motion,
   loading/error/empty states, a polished interactive preview, and no placeholders.
2. **Business vision** — a plan visibly tied to the prompt, real user journeys,
   actors, business outcomes, authorization/ownership, scope boundary, concrete API
   vocabulary, and frontend/backend handoff evidence.
3. **Rigid backend** — persistent SQLAlchemy model, authentication/authorization,
   validation, CORS, health route, CRUD surface, generated API tests, integration
   artifacts, CI, deployment checklist, and executable QA/build verification where
   a project workspace is available.

The gate is binary: `score: 100` only when every vertical passes. Any violation fails
the pipeline instead of labelling a scaffold as complete. This is default behavior
for terse prompts such as `build an app similar to Zoho` as well as detailed briefs.
