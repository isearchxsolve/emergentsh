# Product architecture scaffold

The quality gate is backed by a deterministic `PRODUCT_BLUEPRINT.json`, created
before the Planner calls a model. Terse prompts receive a category baseline:

- business suite / Zoho / CRM / ERP: organizations, contacts, work items,
  activity timeline, search, and owner/manager/member roles;
- commerce: catalog, cart, orders, inventory, customer history;
- booking: availability, booking, confirmation, calendar, cancellation;
- workspace: workspace, records, assignment, activity timeline, search;
- unknown product: safe persistent-record, workflow, timeline, search, settings
  and owner/member baseline.

The Planner receives the blueprint with the product-discovery contract and writes
`ARCHITECTURE.md`; the Frontend and Backend agents both receive the same blueprint.
It is an out-of-the-box starting architecture, not a replacement for product-specific
reasoning. The strict quality gate rejects an incomplete implementation afterward.
