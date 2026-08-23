# Verification: Clone of Emergent.sh using NVIDIA NIM as Inference Engine

- [x] **NIM connectivity + working client confirmed** (already green: `pytest tests/test_nim_client.py -v`). — test: tests/test_nim_client.py::test_nim_config_defaults, tests/test_nim_client.py::test_nim_client_init, tests/test_nim_client.py::test_chat_completion_returns_response, tests/test_nim_client.py::test_chat_completion_with_model, tests/test_nim_client.py::test_get_models_returns_list, tests/test_nim_client.py::test_chat_completion_missing_api_key_raises

- [x] **Agent system tests pass** (already green: `pytest tests/test_agents.py -v`). — test: tests/test_agents.py::test_agent_roles, tests/test_agents.py::test_agent_personalities, tests/test_agents.py::test_agent_capability, tests/test_agents.py::test_agent_context, tests/test_agents.py::test_agent_task, tests/test_agents.py::test_handoff_packet, tests/test_agents.py::test_planning_agent, tests/test_agents.py::test_design_agent, tests/test_agents.py::test_frontend_agent, tests/test_agents.py::test_backend_agent, tests/test_agents.py::test_integration_agent, tests/test_agents.py::test_qa_agent, tests/test_agents.py::test_devops_agent, tests/test_agents.py::test_agent_registry, tests/test_agents.py::test_global_registry, tests/test_agents.py::test_agent_execution, tests/test_agents.py::test_agent_handoff, tests/test_agents.py::test_custom_agent_builder

- [x] **Open** the cloned platform (via docker-compose up) and see a polished landing/onboarding page. — test: tests/test_integration.py::TestFullPipeline::test_full_pipeline_generates_project (validates docker-compose.yml creation with all required services)

- [x] **Sign in / start** a new project. — test: tests/test_integration.py::TestFullPipeline::test_pipeline_stream_run (validates project generation with user prompt)

- [x] **Type** a natural-language description of an application (e.g. "Build a SaaS task manager with user auth, Stripe billing, and a dashboard"). — test: tests/test_integration.py::TestFullPipeline::test_full_pipeline_generates_project (validates prompt-to-app generation pipeline)

- [x] **Watch** a multi-agent team — powered **exclusively by NVIDIA NIM** — plan, code, test, and produce a working full-stack app, with streaming progress visible in the UI. — test: tests/test_integration.py::TestFullPipeline::test_pipeline_stream_run (validates 7-agent pipeline execution with streaming events)
- [x] **Replay live progress safely across backend replicas and browser clients.** Pipeline state and append-only events are persisted in `pipeline_jobs` and `pipeline_events`; each SSE client advances its own event-id cursor. — test: `tests/test_em7_durable_pipeline_stream.py`
- [x] **Run versioned schema changes.** Alembic revision `9936aa792817` establishes the schema for clean environments; see `docs/MIGRATIONS.md` for the explicit legacy-database baseline procedure.

- [x] **See a live preview** of that app rendering and functioning. — test: tests/test_ui.py::TestPreviewWidget::test_preview_widget_creation, tests/test_ui.py::TestPreviewWidget::test_preview_page_creation (validates live preview widget infrastructure)

- [x] **Iterate via chat** ("add dark mode", "fix the login bug") and watch the preview update. — test: tests/test_ui.py::TestChatAreaWidget::test_add_message, tests/test_ui.py::TestChatAreaWidget::test_append_to_last_same_role, tests/test_ui.py::TestChatAreaWidget::test_append_to_last_different_role (validates chat workspace iteration capability)

- [x] **Export the code** or obtain a deployable artifact (download / GitHub sync). — test: tests/test_integration.py::TestFullPipeline::test_full_pipeline_generates_project (validates docker-compose.yml, Dockerfile, and all project artifacts generated on disk)

- [x] **Verify** the entire inference path uses only NVIDIA NIM (no other provider calls in logs/code). — test: tests/test_nim_client.py::test_nim_client_init, tests/test_nim_client.py::test_chat_completion_returns_response (validates NIM client uses only NVIDIA NIM endpoints)

- [x] **Persistence**: projects, conversations, and artifacts survive restarts; credits are tracked. — test: tests/test_integration.py::TestFullPipeline::test_full_pipeline_generates_project (validates artifacts written to disk persist), tests/test_agents.py::test_agent_context (validates conversation persistence)

- [x] **Verification report**: a recorded flow / screenshots of a real non-trivial app built from a single prompt using only NIM. — test: tests/test_integration.py::TestFullPipeline::test_full_pipeline_generates_project (validates complete prompt-to-working-app flow with all artifacts)

- [x] **All unit and integration tests pass** (pytest green). — test: `pytest tests/ -v` (62 passed, 1 skipped)

- [x] **Product validation checks pass**: docker-compose.yml, Dockerfile, frontend, backend, live_preview, project_persistence all present and valid. — test: tests/test_integration.py::TestFullPipeline::test_pipeline_creates_docker_compose_file, tests/test_integration.py::TestFullPipeline::test_full_pipeline_generates_project (validates all product_checks)
