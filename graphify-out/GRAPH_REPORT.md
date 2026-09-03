# Graph Report - delivery-value-dashboard  (2026-09-03)

## Corpus Check
- 148 files · ~479,321 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2023 nodes · 3833 edges · 115 communities (98 shown, 16 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 198 edges (avg confidence: 0.88)
- Token cost: 1,097,485 input · 0 output

## Community Hubs (Navigation)
- Calculator Service Routes
- Forge Resolver & Jira Reads
- Weekly Brief Composition
- Forge Async Jobs
- Facts Pack Metrics
- Durable Series & Audit
- Organisation Config
- Agent Tool Tests
- WebAssembly In-Function Runtime
- Calculator Deploy & Provisioning
- Dashboard Forecast Rendering
- Forge Context Parsing
- Service Contract Tests
- Monte Carlo Forecaster
- ADR Index & Permission Records
- Jira OAuth Login
- Build & Security Suite
- Import Column Mapping Screen
- Import Pipeline
- Scope Allow-list Tests
- Hosting & Realms
- Live Mode Server
- Issue Selection & Slicing
- Dashboard Charts & Drilldowns
- Forge Package Dependencies
- WASM Parity & CI
- Intake Ask 030
- Agent Skill & Constraints
- Dashboard Screenshot
- Dashboard Context Loading
- Brief Delivery via Jira
- Intake Forecasting
- Intake Ask 014
- Intake Ask 015
- Root Package Manifest
- Business Value Counting
- Foundational ADRs
- Forecasting Agent Design
- Delivery Data Fetcher
- Jira Client Fields
- Tile Picker & Presets
- End-to-end Suite
- Candidacy & Value Basis
- Data Format & History Rows
- Intake Ask 016
- Live Jira Backend
- Product Intake Concepts
- Bridge Adapter Transport
- Runs on Atlassian Research
- Forecast Log & Calibration
- T-shirt Sizing Ladder
- Sequencing Without Scores
- Async Jobs & No Arithmetic
- Forge App Manifest
- Import Preview Screen
- Units & Forecasting Rules
- Subtask Counting
- Empty Selection Refusals
- Connecting Jira & Asana
- Bundle Backend
- Dashboard Org Config Mirror
- Cross-team Rollup View
- Page Shell & Flow Health
- Custom Fields & Sizing
- Hosted Calculator Overview
- Context Picker Screenshot
- Commitment Recommendation
- People Picker
- Scopes & Job Status
- Flow Board Glossary
- Output Escaping & XSS
- Commercial Roadmap
- Jira Token Transport
- WASM Test Harness
- Org Config Documentation
- Manifest Wiring Tests
- Flow Tiles & No People Metrics
- Refuse Rather Than Widen
- Sample Bundle Generator
- Service Computes Nothing Tests
- Forge Deployment Guide
- Dashboard Review Notes
- Connection Probe
- Demo Recording Script
- Candidate Asks Mirror
- Accessibility Suite
- Import Wizard Concepts
- Plausible Wrong Number Class
- Forge Permissions
- Window Forecast Tests
- Intake Demo Generator
- Weekly Brief Function
- Forecast Claims
- Flow Time Glossary
- Issue Tracker & Labels
- Recipient Validator Parity
- Two Transports Parity Test
- Series Refusal Checks
- Performance Suite
- Recipient Picker Notes
- Queue Cost Scenarios
- Refresh Script
- Counting Checks
- Forge Dependency Test
- Brief Shape Test
- Send Guards Test
- Name Lookup Test
- Served Burndown Test
- Manifest Matches Code Test
- Ageing
- Risk Register
- Scope Growth
- Intake Reproducibility
- Intake Blind Spots

## God Nodes (most connected - your core abstractions)
1. `check()` - 53 edges
2. `render()` - 42 edges
3. `Decision records index` - 33 edges
4. `ADR 0031: The forecast runs inside the Forge function` - 29 edges
5. `check()` - 28 edges
6. `ADR 0008: Forge calls a hosted calculator` - 27 edges
7. `build()` - 25 edges
8. `sequence()` - 25 edges
9. `Hosting the calculator` - 25 edges
10. `ADR 0009: One contract, two transports` - 21 edges

## Surprising Connections (you probably didn't know these)
- `People picker searches by name, stores the id, projects to an allow-list of fields` --semantically_similar_to--> `clean_dataset()`  [AMBIGUOUS] [semantically similar]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md → service/routes.py
- `size_stability(): the interchangeable-items assumption is checked` --references--> `size_stability()`  [AMBIGUOUS]
  docs/adr/0006-forecast-in-items-not-points.md → agent/tools/forecast.py
- `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)` --references--> `clean_dataset()`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md → service/routes.py
- `Size stability` --references--> `size_stability()`  [INFERRED]
  CONTEXT.md → agent/tools/forecast.py
- `size_stability: drift and spread guard on item counting` --references--> `size_stability()`  [EXTRACTED]
  docs/forecasting-agent.md → agent/tools/forecast.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Retiring the calculator: the Python runs inside the Forge function** — changelog_forge_pyodide_in_function, changelog_sequencing_as_async_job, changelog_forecast_as_job_chunked_payload, changelog_wasm_parity_suite, changelog_python_runtime_as_generated_module, changelog_routes_py_split_from_app_py, forge_src_runtime, forge_src_jobs, forge_build_assets, service_routes, tests_test_wasm, docs_adr_0031_the_forecast_runs_inside_the_forge_function, context_calculator [EXTRACTED 1.00]
- **One implementation of every figure: nothing between a tool and a reader computes** — claude_agent_never_does_arithmetic, claude_no_arithmetic_between_tools_and_reader, claude_org_config_travels_inside_data, changelog_forecast_tile_served, changelog_hosted_calculator_projection, changelog_model_never_writes_a_number, changelog_burndown_served_by_calculator, changelog_history_row_moved_to_metrics, changelog_slice_route, agent_skill_delivery_report, docs_adr_0005_tools_compute_the_agent_narrates [INFERRED 0.85]
- **Refuse rather than widen: empty, unmeasured and thin evidence all refuse in the tool's own words** — claude_refusals_printed_verbatim, claude_empty_selection_is_a_refusal, claude_refusal_thresholds_are_hard, context_refusal, changelog_empty_sprint_scored_66, changelog_unmeasured_component_dropped, changelog_refusal_carries_its_unit, changelog_sprint_length_fallback_removed, agent_skill_refusal_thresholds, docs_adr_0010_an_empty_selection_is_a_refusal, docs_adr_0007_refuse_rather_than_widen [INFERRED 0.85]
- **Allow-list projection: stores and payloads hold named fields only, never issue text or contact details** — docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_scope_allow_list, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_people_picker_allow_list, docs_adr_0015_a_durable_series_stores_what_jira_forgets_counts_never_issue_text, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_claim_fields_allow_list, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_app_store_inventory, docs_adr_0021_the_audit_log_is_operational_and_says_so_audit_entry_allow_list [INFERRED 0.85]
- **Refusal family: below the evidence, say the evidence is absent rather than print a plausible figure** — docs_adr_0007_refuse_rather_than_widen_refuse_rather_than_widen, docs_adr_0007_refuse_rather_than_widen_evidence_absent_not_noisy, docs_adr_0010_an_empty_selection_is_a_refusal_empty_selection_refusal, docs_adr_0011_a_kanban_context_is_a_window_not_a_clock_window_not_a_clock, docs_adr_0013_the_brief_is_written_inside_the_tenant_refusals_not_passed_through_model, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_refusal_not_a_claim [EXTRACTED 1.00]
- **Roadmap item 5: permission mirroring, its three exposures and their accepted answers** — docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_permission_mirroring_by_asuser, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_three_exposures, docs_adr_0019_a_recorded_row_is_a_fact_about_the_board_row_belongs_to_board, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_anchor_issue_access_control, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_restrict_browse, docs_adr_0013_the_brief_is_written_inside_the_tenant_asapp_reversal, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_offline_user_impersonation_deferred [EXTRACTED 1.00]
- **The four custom fields the app declares** — docs_adr_0025_the_app_declares_a_business_value_field_business_value_field, docs_adr_0027_a_value_basis_is_prose_carried_to_a_reader_value_basis_field, docs_adr_0028_candidacy_is_a_state_somebody_declares_candidate_field, docs_adr_0029_a_t_shirt_band_selects_a_reference_class_size_field, docs_forge_deployment_four_custom_fields_and_screens [EXTRACTED 1.00]
- **Forge async job flow for forecast and sequencing** — docs_adr_0031_the_forecast_runs_inside_the_forge_function_async_job_pattern, docs_adr_0031_the_forecast_runs_inside_the_forge_function_forecast_is_async_correction, docs_adr_0031_the_forecast_runs_inside_the_forge_function_twelve_ask_cap, docs_adr_0031_the_forecast_runs_inside_the_forge_function_retry_guard, docs_adr_0031_the_forecast_runs_inside_the_forge_function_job_row [EXTRACTED 1.00]
- **Decisions driven by the credible-wrong-number failure class** — docs_adr_0023_a_cross_team_rollup_spans_what_the_reader_can_see_rollup_does_not_forecast, docs_adr_0024_a_parent_and_its_subtasks_are_one_piece_of_work_count_subtasks, docs_adr_0026_items_and_value_are_counted_from_two_different_sets_two_sets_items_and_value, docs_adr_0030_the_manifest_commits_to_its_hostnames_and_realms_once_region_added_via_deploy_loop, docs_hosting_the_calculator_forecast_slice_in_selection_py, docs_forecasting_agent_reporting_scope_is_not_forecasting_scope [INFERRED 0.85]
- **Connection check: bridge, read board, projection** — forge_probe_index_bridge_check, forge_probe_index_read_board, forge_probe_index_projection_check, forge_manifest_connection_check_adminpage [EXTRACTED 1.00]
- **The four declared Jira custom fields (value, basis, candidate, band)** — forge_manifest_business_value_field, forge_manifest_value_basis_field, forge_manifest_candidate_field, forge_manifest_tshirt_size_field, docs_roadmap_item_7_rollup_and_sequencing [EXTRACTED 1.00]
- **Pyodide-in-function route: research, probes, manifest functions** — docs_research_2026_09_01_runs_on_atlassian_badge_pyodide_in_forge_function, docs_research_2026_09_02_second_probe_consumer_and_snapshot_wasm_probe_2, docs_research_2026_09_01_forge_async_events_consumer_module, forge_manifest_resolver_function, forge_manifest_simulation_fn, forge_manifest_simulation_consumer, service_readme_routes_py_travels [INFERRED 0.95]
- **Source > Project > Board > Sprint selection cascade** — docs_screenshots_context_picker_source_badge, docs_screenshots_context_picker_project_selector, docs_screenshots_context_picker_board_selector, docs_screenshots_context_picker_sprint_selector [INFERRED 0.85]
- **Dashboard header strip** — docs_screenshots_context_picker_header_line, docs_screenshots_context_picker_sprint_goal, docs_screenshots_context_picker_data_bundle_pill, docs_screenshots_context_picker_sprint_health_pill, docs_screenshots_context_picker_toolbar_actions [EXTRACTED 1.00]
- **Narrative panel, KPI tiles and risk list are three views of the same sprint facts** — docs_screenshots_dashboard_what_this_sprint_means, docs_screenshots_dashboard_kpi_tiles, docs_screenshots_dashboard_risks_and_what_to_do [INFERRED 0.85]
- **Flow charts: burndown, cycle time with waiting, work item age** — docs_screenshots_dashboard_burndown_with_scope_changes, docs_screenshots_dashboard_cycle_time_waiting_chart, docs_screenshots_dashboard_work_item_age [INFERRED 0.75]
- **CSV import wizard: upload, check column mapping, load** — docs_screenshots_import_mapping_upload_a_file_tab, docs_screenshots_import_mapping_step_2_of_3_check_column_mapping, docs_screenshots_import_mapping_column_mapping_table, docs_screenshots_import_mapping_jira_export_csv [EXTRACTED 1.00]
- **Created, started and resolved dates drive lead time, cycle time and burndown** — docs_screenshots_import_mapping_created_date_field, docs_screenshots_import_mapping_started_date_field, docs_screenshots_import_mapping_resolved_date_field, docs_screenshots_import_mapping_lead_time_metric, docs_screenshots_import_mapping_cycle_time_metric, docs_screenshots_import_mapping_burndown_metric [EXTRACTED 1.00]
- **Import wizard step 3: review counts, warnings and preview rows before applying** — docs_screenshots_import_preview_step_3_check_before_applying, docs_screenshots_import_preview_summary_tiles, docs_screenshots_import_preview_no_business_value_warning, docs_screenshots_import_preview_preview_table, docs_screenshots_import_preview_apply_to_the_dashboard [EXTRACTED 1.00]
- **Three ways in: upload a file, connect Jira/Asana, read the data format** — docs_screenshots_import_preview_upload_a_file_tab, docs_screenshots_import_preview_connect_jira_asana_tab, docs_screenshots_import_preview_data_format_tab [EXTRACTED 1.00]

## Communities (115 total, 16 thin omitted)

### Community 0 - "Calculator Service Routes"
Cohesion: 0.06
Nodes (64): Auth mode chosen by FORGE_AUDIENCE, BaseHTTPRequestHandler, The calculator verifies Forge invocation tokens (1.18.0-1.21.0), service/routes.py split from app.py (1.76.0), assertAsksCarryNoText / _refuse_ask_text, Forge invocation token verifier (_verify_forge_token), The tenant claim is nested at app.installationId, Exception (+56 more)

### Community 1 - "Forge Resolver & Jira Reads"
Cohesion: 0.06
Nodes (54): The calculator is reached by invokeRemote (1.19.0), Business Value custom field (jira:customField), appFieldsFor(), ASK_TEXT_FIELDS, assertNoFreeText(), boardEpicsFor(), boardFigures(), boardProject() (+46 more)

### Community 2 - "Weekly Brief Composition"
Cohesion: 0.07
Nodes (56): ADR-0005, ADR-0007, forge/src/compose.js keeps the send provable without deploying, briefMessages(), composeBrief(), contentText(), DECLINED, deliveryBlockers() (+48 more)

### Community 3 - "Forge Async Jobs"
Cohesion: 0.06
Nodes (58): ADR-0018, Consumer function limits: 900 s, 1,024 MB, Forge consumer module, Documented major-version change list, A resolver returns before its pushed work completes, Adding a consumer is a minor version; a remote is major, consumer simulation-consumer (queue: simulations), function simulation-fn (900 s, 1,024 MB) (+50 more)

### Community 4 - "Facts Pack Metrics"
Cohesion: 0.05
Nodes (50): burndown(), _d(), diff(), elapsed_days(), facts(), _get(), history_series(), in_sprint() (+42 more)

### Community 5 - "Durable Series & Audit"
Cohesion: 0.06
Nodes (50): creditableEpics reports what it excluded via valueWindow (1.71.0), problemsInAuditEntry: counts, flags, field names, one actor identity, appendAudit(), AUDIT_EVENTS, AUDIT_FIELDS, AUDIT_KEY, auditEntry(), auditNote() (+42 more)

### Community 6 - "Organisation Config"
Cohesion: 0.06
Nodes (45): meta.calendar must equal inputs.calendar, add_working_days(), candidate_answer(), candidate_issues(), counted_note(), from_dataset(), holiday_set(), is_done() (+37 more)

### Community 7 - "Agent Tool Tests"
Cohesion: 0.07
Nodes (47): check(), _intake_ds(), near(), An unauthenticated pull must stop, not degrade — found against live Jira.…, The facts pack reports the sprint; the forecaster uses all history. Conflating…, `/rest/api/3/search` was removed; `/search/jql` pages by token. Not a URL swap.…, The three ways a forecast can be built from the wrong slice of the file. All…, The headline output: is the range driven by not knowing the size, or by normal… (+39 more)

### Community 8 - "WebAssembly In-Function Runtime"
Cohesion: 0.06
Nodes (44): The forecast runs inside the Forge function (1.75.0-1.77.3), Python runtime packed into forge/src/assets.js (1.76.1), WebAssembly parity suite tests/test_wasm.py (1.76.2), Calculator, ADR 0031: The forecast runs inside the Forge function, Async job: resolver pushes, consumer computes, adapter polls, Correction 2026-09-03: the forecast is asynchronous too, Job row in app storage (+36 more)

### Community 9 - "Calculator Deploy & Provisioning"
Cohesion: 0.09
Nodes (40): CI container job, Cloud Run deploy flags, Calculator deploy job, REGIONS named once, /v1/meta 401 post-deploy probe, Weekly rebuild that deploys, Workload Identity Federation deploy auth, The calculator is hosted on Cloud Run (1.20.0-1.20.3) (+32 more)

### Community 10 - "Dashboard Forecast Rendering"
Cohesion: 0.07
Nodes (37): ADR-0004, ADR-0023, auditHtml(), bindForecastInputs(), briefAudienceFields(), briefBoard(), briefList(), fcKey() (+29 more)

### Community 11 - "Forge Context Parsing"
Cohesion: 0.06
Nodes (42): ADR-0029, No text from the page reaches Jira, addedMidSprint(), basisOf(), BUSINESS_VALUE_KEY, CALENDAR_NOTE, CANDIDATE_KEY, CANDIDATE_NO (+34 more)

### Community 12 - "Service Contract Tests"
Cohesion: 0.05
Nodes (37): ask_assembly_checks(), audit_log_checks(), body_keys_reach_a_reader(), business_value_checks(), check(), cross_team_checks(), forecast_log_checks(), permission_mirroring_checks() (+29 more)

### Community 13 - "Monte Carlo Forecaster"
Cohesion: 0.13
Nodes (33): add_working_days(), build(), CountForecast, cycle_times(), _d(), DateForecast, forecast_completion(), forecast_count_by_date() (+25 more)

### Community 14 - "ADR Index & Permission Records"
Cohesion: 0.11
Nodes (34): Activity log, deliberately not called an audit log (1.48.0), The anchor issue is the brief's access control (1.47.0), Forecast log claims carry view width (1.46.0), Permission mirroring holds by accident where nothing is kept (1.44.0), The store holds counts, never issue text, ADR 0017: A forecast is logged as a count not a promise, CLAIM_FIELDS allow-list; problems_in_claim refuses rather than trims, A claim's id is deterministic: context, day, percentile (+26 more)

### Community 15 - "Jira OAuth Login"
Cohesion: 0.11
Nodes (22): Jira connects over OAuth 2.0 3LO (1.14.0), SSO needs nothing built (1.49.0), The personal API token path lives only in scripts/, accessible_resources(), authorize_url(), _Catcher, _client(), ensure_token() (+14 more)

### Community 16 - "Build & Security Suite"
Cohesion: 0.13
Nodes (28): GitHub Pages publish job, build(), build_split(), main(), The same sources as separate files, for a host that forbids inline assets. The…, The Pages workflow is workflow_dispatch only (1.8.1), Credentials live only in the fetcher's environment, The Forge build is a split build, not a copy of dist/ (+20 more)

### Community 17 - "Import Column Mapping Screen"
Cohesion: 0.08
Nodes (30): Import mapping screenshot, Assignee field, Auto-detected mapping (green check status), Burndown and completion, Column mapping table (Dashboard field / Your column / Example value / Status), Connect Jira / Asana tab, Created date field (drives ageing and lead time), Custom field mapping (story points, started date) (+22 more)

### Community 18 - "Import Pipeline"
Cohesion: 0.12
Nodes (25): Import problem issue template, Import pipeline: parse, map, coerce, assemble, Three routes for getting data in, assemble(), autoMap(), buildBurndown(), buildHistoryRow(), buildIssues() (+17 more)

### Community 19 - "Scope Allow-list Tests"
Cohesion: 0.08
Nodes (27): The read-only rule becomes an allow-list with justifications, Every app-level store is declared in tests/test_service.py with its authority, _jwt_available(), The projection exists in two languages and they must not drift.…, A flow board's window must be one object, not two that look alike. A board that…, SERVICE_AUTH=forge-token, proved without Atlassian. A keypair is generated…, A calculator that came up open would look perfectly healthy., The scheduled brief's guard: the model writes the sentences, never the numbers.… (+19 more)

### Community 20 - "Hosting & Realms"
Cohesion: 0.11
Nodes (27): Manifest realm deploy guard, Calculator keeps its *.run.app hostnames (1.73.0), GB realm declared with its own London service (1.73.0-1.74.1), forge/manifest.yml triggers the deploy for the guard (1.74.2), Module type or scope change is a major version, ADR 0030: The manifest commits to its hostnames and realms once, Rule: move the Google Cloud project, never recreate it, A third region is a change to deploy.yml's region loop (+19 more)

### Community 21 - "Live Mode Server"
Cohesion: 0.12
Nodes (22): append_audit(), Handler, A mirror of `problemsIn` in forge/src/recipients.js, in Python. A second…, One board's recorded rows. Missing and unreadable both read as empty. Keyed by…, One board's forecast log. Missing and unreadable both read as empty — a caller…, Mirrors `appendAudit` in forge/src/audit.js, bound included. Best-effort and…, Whether this observation may be written. Mirrors `recordable` in…, The trend series for the board `cid` belongs to, and the recording of it. The… (+14 more)

### Community 22 - "Issue Selection & Slicing"
Cohesion: 0.13
Nodes (24): cross_team_boards(), cross_team_label(), cross_team_members(), forecast_for(), Which issues a forecast reads, and what it is told about them. This is the…, The context a forecast is *for*, and the sprints a rollup stands for. Returns…, Which contexts a forecast for `cid` would sample, and how it chose them.…, Run the real forecaster for one context. Returns None for an unknown id. The… (+16 more)

### Community 23 - "Dashboard Charts & Drilldowns"
Cohesion: 0.20
Nodes (24): Drill-down, cycleRows(), drawTable(), littlesLaw(), openDrill(), pctile(), renderAge(), renderBurn() (+16 more)

### Community 24 - "Forge Package Dependencies"
Cohesion: 0.08
Nodes (23): esbuild, @forge/api, @forge/bridge, @forge/events, @forge/kvs, @forge/llm, dependencies, @forge/api (+15 more)

### Community 25 - "WASM Parity & CI"
Cohesion: 0.16
Nodes (22): CI build job, dist/ is committed on purpose, _intake_bodies(), project(), The measurement the architecture is built on, asserted rather than recalled.…, The demo intake bundle, projected, and its asks stripped of every word. What…, One seam, two doors. ADR 0031. `service/routes.py` is what travels into the…, One team's slice, projected — exactly what the Forge resolver sends. (+14 more)

### Community 26 - "Intake Ask 030"
Cohesion: 0.09
Nodes (22): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+14 more)

### Community 27 - "Agent Skill & Constraints"
Cohesion: 0.12
Nodes (22): Sprint 24 delivery brief (worked example), Sprint 24 team report (worked example), delivery-report agent skill, Prohibited outputs, Agent refusal thresholds, Exec brief template, Team report template, Refusal carries the unit it counted in (1.71.0) (+14 more)

### Community 28 - "Dashboard Screenshot"
Cohesion: 0.11
Nodes (22): Dashboard screenshot (Sprint 24 — delivery and value), Burndown with scope changes shown, Business value delivered ($34,800 estimated, with stated basis), Can we trust the forecast? (committed vs completed, last six sprints), How long work takes and how much is waiting (flow efficiency per closed item), Every figure traces back to an issue (footer principle, click-through links), Filter row (Source, Project, Board, Sprint, Person, Epic, Type, Status, Find), Flow efficiency (32% of elapsed time was active work) (+14 more)

### Community 29 - "Dashboard Context Loading"
Cohesion: 0.15
Nodes (22): commitU(), fetchSeries(), filtered(), loadContext(), loadRollupMembers(), orgSummary(), probeLive(), refreshLive() (+14 more)

### Community 30 - "Brief Delivery via Jira"
Cohesion: 0.13
Nodes (21): agent/SKILL.md, A brief was delivered through Jira (1.30.0-1.32.0), Forge LLMs write the brief inside the tenant (1.24.0), Jira sends the brief through /notify (1.26.0), The model never writes a number (1.24.0), The scheduled brief reads the board as the app (1.29.0), Mail subject flattened against header injection (1.27.0), A negative result from synthetic input against an embedded frame is not evidence (1.29.1-1.29.5) (+13 more)

### Community 31 - "Intake Forecasting"
Cohesion: 0.18
Nodes (20): attribute_uncertainty(), board_issues(), capacity(), _d(), epic_sizes(), _fmt(), _fmt_sequence(), forecast_ask() (+12 more)

### Community 32 - "Intake Ask 014"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 33 - "Intake Ask 015"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 34 - "Root Package Manifest"
Cohesion: 0.10
Nodes (20): description, engines, node, keywords, license, name, private, scripts (+12 more)

### Community 35 - "Business Value Counting"
Cohesion: 0.14
Nodes (19): Whether this issue's business value is counted — ADR 0025. Value belongs at one…, One issue's business value as it should be counted, or zero. The one place the…, The issues whose business value is counted — the *other* pool. Items and value…, value_counts(), value_issues(), value_of(), The app declares a Business Value field (1.54.0), Candidates were filtered out by the resolution-date window (1.66.1) (+11 more)

### Community 36 - "Foundational ADRs"
Cohesion: 0.16
Nodes (19): ADR 0001: The dashboard is one self-contained HTML file, Threat model: the file gets emailed, Single self-contained HTML file, ADR 0005: Tools compute, the agent narrates, Tools compute; the agent narrates, ADR 0008: Forge calls a hosted calculator, Forge CSP forbids inline style/script; split build and CSSOM setter wrap, Hosted calculator imports the Python tools unchanged (+11 more)

### Community 37 - "Forecasting Agent Design"
Cohesion: 0.12
Nodes (19): ADR 0006: Forecasts count items, never story points, Forecasts count items, never story points, size_stability(): the interchangeable-items assumption is checked, ADR 0029: A t-shirt band selects a reference class, MIN_TSHIRT_EPICS = 8 (vs MIN_REFERENCE_EPICS 5), orgConfig.sizeField, sizing_method / sizing_basis on every ordering row, Units: items by default; calendar days reported, working days simulated (+11 more)

### Community 38 - "Delivery Data Fetcher"
Cohesion: 0.19
Nodes (18): Started date lives in the changelog, not the export, Story points discovered by display name, asana_pull(), build_burndown(), configure(), d(), jira_bundle(), jira_pull() (+10 more)

### Community 39 - "Jira Client Fields"
Cohesion: 0.15
Nodes (9): Jira, The Jira surface this script needs, over either transport. `url` is the…, Who this connection is authenticated as — `(identity, None)`, or `(None, why)`…, Locate the story-point and sprint custom fields by display name., The field that says an issue is an ask — ours, or the site's own. `"app"` is…, The field carrying an ask's t-shirt band — ours, or the site's own. Same rule…, This app's own Business Value and Value Basis fields on this site. **Matched on…, The board's epics as issues — ADR 0026. **Epics are not on a scrum board.**… (+1 more)

### Community 40 - "Tile Picker & Presets"
Cohesion: 0.18
Nodes (19): announcePicker(), applyOrder(), applyTiles(), buildPicker(), buildPickerList(), download(), focusMover(), moveTile() (+11 more)

### Community 41 - "End-to-end Suite"
Cohesion: 0.18
Nodes (18): check(), empty_selection(), flow_board(), health_composition(), main(), open_picker(), A host may forbid inline style, and the page must lose no colour to it. The…, For a check that could not run rather than one that did not hold. Said out… (+10 more)

### Community 42 - "Candidacy & Value Basis"
Cohesion: 0.16
Nodes (18): intake.candidate_answer, A declared candidate becomes an ask (1.65.0), A t-shirt band declares candidacy (1.69.0), The app declares a Candidate field (1.63.0), Forge sequencing delegates to /v1/sequence (1.66.0), Value and basis rendered on the sequencing tile (1.67.0), The app declares a Value Basis field, free text (1.57.0), Candidate (+10 more)

### Community 43 - "Data Format & History Rows"
Cohesion: 0.17
Nodes (18): history_row(), One sprint's row of the trend series, as it stood at `as_of`. **Every count…, history_row moved into agent/tools/metrics.py (1.37.0), History rows derived from dates keyed to a moment (1.36.0), A recorded row records how wide the view was (1.45.0), trendSprints replaces three silent six-sprint caps (1.43.0), A Forge tenant has a trend (1.38.0-1.39.2), Durable series (+10 more)

### Community 44 - "Intake Ask 016"
Cohesion: 0.11
Nodes (17): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+9 more)

### Community 45 - "Live Jira Backend"
Cohesion: 0.14
Nodes (11): JiraBackend, The third part of a flow board's context id. Prefixed rather than bare, so a…, Which issues are *in* a window, as a JQL predicate. The membership ADR 0011…, One selectable window, in the shape the sprint entry above uses. Field for…, Queries Jira on demand. Sprint lists are cheap; issues are fetched only when a…, The saved filter behind a board, which is how plain JQL is scoped to one. The…, Sequencing sizes asks against the board's completed epics and its interruption…, Unlike the bundle, this has to fetch. A forecast needs the team's whole… (+3 more)

### Community 46 - "Product Intake Concepts"
Cohesion: 0.17
Nodes (17): Intake mode, Intake brief template, readiness(), Three intake scope bugs returned plausible wrong numbers (1.8.0), Product intake forecasts an ask before tickets exist (1.8.0), Never compute a priority score, Value basis is free text carried to a reader, Ask (+9 more)

### Community 47 - "Bridge Adapter Transport"
Cohesion: 0.15
Nodes (14): The dashboard inside Forge shows the customer's own Jira (1.16.0), Live mode: one contract, two transports, Live mode, ADR 0009: One contract, two transports, Forge bridge adapter (window.__DVD_BRIDGE__), The resolver plays the fetcher's part, not the calculator's, Live mode via scripts/serve_live.py, The bridge adapter (forge/bridge/bridge.js) (+6 more)

### Community 48 - "Runs on Atlassian Research"
Cohesion: 0.13
Nodes (17): Research note: async events for sequencing (2026-09-01), CPython WASI as an alternative, The Forge bundler drops .wasm and stdlib zip, Local Pyodide measurement on M3 Pro, Pyodide inside a Forge function, Declaring a remote costs eligibility before any traffic, Research note: recovering the Runs on Atlassian badge (2026-09-01), Runs on Atlassian eligibility criteria (+9 more)

### Community 49 - "Forecast Log & Calibration"
Cohesion: 0.13
Nodes (16): calibration_note(), _narrow_sentence(), problems_in_claim(), What is wrong with one logged claim, as sentences. Empty means storable.…, Score every claim whose horizon has passed, from completions in its window.…, What a reader is told above a calibration score, or instead of one. The…, What is said when this reader's view was too narrow to publish. Silent when it…, Score past forecasts against what actually happened. Without this the agent is… (+8 more)

### Community 50 - "T-shirt Sizing Ladder"
Cohesion: 0.17
Nodes (15): Derive S/M/L/XL bands from the team's own completed epics. Quartiles, not a…, Turn a product ask into a distribution of item counts., Refusal, size_ask(), Sizing, _triangular(), tshirt_scale(), T-shirt band selects a quartile of completed epics (1.68.0) (+7 more)

### Community 51 - "Sequencing Without Scores"
Cohesion: 0.17
Nodes (16): The refusal sentence for more asks than one sequencing compares, or None. A…, For a set of asks against one team, what each ordering costs the others.…, sequence(), too_many_asks(), ADR 0004: No priority score, Delivery consequence of an ordering, No WSJF or value-over-effort priority score, What an ask is inside Jira (open product question) (+8 more)

### Community 52 - "Async Jobs & No Arithmetic"
Cohesion: 0.15
Nodes (16): schemaVersion 2.0 bundle format with contexts (1.5.0), Sizing groups epics by epicKey when names are stripped (1.17.1), The forecast is a job with a chunked payload (1.77.3), The Monte Carlo tile is served, not reimplemented (1.10.0), The simulation horizon is named when trials abandon (1.11.0), The hosted calculator takes a projection and refuses free text (1.15.0), Live server dropped the connection on any 404 (1.9.1), Sequencing runs as an async job (1.77.0) (+8 more)

### Community 53 - "Forge App Manifest"
Cohesion: 0.14
Nodes (16): Pyodide memory snapshot trade-off, Item 1: OAuth app on the Marketplace, jira:adminPage connection-check, jira:projectPage delivery-value-dashboard, resource main (static/dashboard/build), Forge app manifest, resource probe (static/probe), function resolver (index.handler, 1,024 MB) (+8 more)

### Community 54 - "Import Preview Screen"
Cohesion: 0.16
Nodes (16): Import preview screenshot (Load your own data, step 3 of 3), Truncation notice: ...and 14 more, Apply to the dashboard button, Back to mapping button, Connect Jira / Asana tab, Data format tab, Sprint 24 demo dashboard behind the modal (Demo data, no live connection), Load your own data modal (+8 more)

### Community 55 - "Units & Forecasting Rules"
Cohesion: 0.14
Nodes (15): Evidence tagging, Forecasting rules, Agent sequence: load, diff, forecast, reconcile, write, log, score, Reporting and forecasting agent introduced (1.2.0), Item counts made the unit end to end (1.3.0/1.4.0), Every figure carries its unit, Forecasts are in items, never story points, Diff (+7 more)

### Community 56 - "Subtask Counting"
Cohesion: 0.20
Nodes (14): counted_issues(), The issues that count as items, and what was left out. Returns `(kept,…, Issue-type filter that changes what is counted (1.53.0), Subtasks were counted as items everywhere (1.52.0), A parent and its subtasks are one item, ADR 0024: A parent and its subtasks are one piece of work, orgConfig.countSubtasks (default false), orgConfig.countedTypes allow-list (default empty) (+6 more)

### Community 57 - "Empty Selection Refusals"
Cohesion: 0.22
Nodes (14): The dashboard scored an empty sprint 66/100 (1.16.1), A missing calendar was scored as bad delivery (1.16.2), An empty selection is a refusal, not a zero, ADR 0010: An empty selection is a refusal, A composite drops an unmeasurable component and names it, Below half the weight the composite refuses, A single 'no data' banner and dimming were rejected, ADR 0011: A kanban context is a window not a clock (+6 more)

### Community 58 - "Connecting Jira & Asana"
Cohesion: 0.14
Nodes (14): ADR 0002: The page never queries Jira or Asana; data arrives as a bundle, Contexts fetched up front into a bundle, Live mode: local server on 127.0.0.1, Connecting Jira and Asana, Fetcher with an API token (scripts/fetch_delivery_data.py), MCP connectors and CSV export routes, OAuth 2.0 (3LO) route via scripts/jira_auth.py, The page cannot call Jira or Asana itself (+6 more)

### Community 59 - "Bundle Backend"
Cohesion: 0.14
Nodes (9): BundleBackend, load_asks(), main(), no_days_yet_note(), Why a sprint's chart has no day on it that has happened yet, or `None`. Mirrors…, Reads an existing bundle file. Used for demos, tests, and for working offline…, Every recorded ask for one board. Read per request rather than cached: an ask…, What each ordering of this board's outstanding asks costs the others. Same tool… (+1 more)

### Community 60 - "Dashboard Org Config Mirror"
Cohesion: 0.22
Nodes (14): applyWorkflow(), boardStatuses(), buildView(), contextWorkingDays(), inferredSentence(), inferredStatuses(), normalise(), ORG() (+6 more)

### Community 61 - "Cross-team Rollup View"
Cohesion: 0.15
Nodes (13): Adding a metric procedure, contextById(), derive(), isWindow(), M_FLOW(), presetOfKind(), reapplyPresetForBoard(), renderExec() (+5 more)

### Community 62 - "Page Shell & Flow Health"
Cohesion: 0.15
Nodes (13): Flow board window context (kind: window), Flow health composite, Sprint health refuses whole on a flow board, Refuse in place versus not shown, Inferred statuses (orgConfig.inferredStatuses), Workflow chip and status mapping control, Build placeholders @@STYLES@@ @@SEED@@ @@APP@@ @@IMPORT@@, Filter bar: person, epic, types, status, find, measure (+5 more)

### Community 63 - "Custom Fields & Sizing"
Cohesion: 0.18
Nodes (13): Epic grouping field chosen once for the whole set, What counts as a finished epic, The sizing ladder (tshirt / reference-class / explicit), T-shirt sizes calibrated per board, Item 7: Cross-team roll-up and intake sequencing, jira:customField Business Value (number), jira:customField Candidate (string), jira:customField T-Shirt Size (string) (+5 more)

### Community 64 - "Hosted Calculator Overview"
Cohesion: 0.17
Nodes (13): PINNED data residency without a remote, Activity log, not audit log, Hostnames and realms settled once, Item 6: SSO, audit log, data residency, remote calculator (region-pinned baseUrl), invokeRemote in forge/src/index.js, requests>=2.31 (fetcher's only dependency), SERVICE_AUTH: shared-secret or forge-token (+5 more)

### Community 65 - "Context Picker Screenshot"
Cohesion: 0.22
Nodes (13): Context picker screenshot, Board selector, Context bar (Source / Project / Board / Sprint), Data-as-at timestamp, Data bundle pill (Demo bundle - 3 boards x 6 sprints), Header line (Project · Team · Sprint dates · data as at), Project selector, Source badge (JIRA) (+5 more)

### Community 66 - "Commitment Recommendation"
Cohesion: 0.20
Nodes (12): How many items can this team commit to in a sprint, and at what confidence?…, recommend_commitment(), Overtime removed, Team load card built from status (1.7.0), The `or 10` sprint-length fallback removed (1.16.4), Zero-throughput days stay in the sample, Commitment recommendation, Interruption rate, Throughput (+4 more)

### Community 67 - "People Picker"
Cohesion: 0.20
Nodes (11): People picker searches by name, stores the id, projects to an allow-list of fields, idsToAsk(), ADR-0014, matchNote(), MAX_MATCHES, MAX_NAMES, namedPerson(), nameNote() (+3 more)

### Community 68 - "Scopes & Job Status"
Cohesion: 0.17
Nodes (12): Async event at-least-once delivery and retries, Forge Realtime as an alternative to polling, Job status is counts only; cancel exists, KVS as the result store for a poller, A timed-out consumer retries in about 40 seconds, Read-only Jira scopes, scope send:notification:jira, scope storage:app (+4 more)

### Community 69 - "Flow Board Glossary"
Cohesion: 0.25
Nodes (11): A board with no sprints gets 14/30/90-day windows (1.16.4-1.16.11), Flow health score for flow boards (1.16.12), Board, Flow board, Flow health, Health score, Period, Sprint (+3 more)

### Community 70 - "Output Escaping & XSS"
Cohesion: 0.24
Nodes (11): Inline style attributes discarded under Forge CSP (1.64.0), Security suite found a real stored XSS (1.7.0), Escape at output, once, Chart colour rules, esc(), issueRow(), normaliseIssue(), noteInferred() (+3 more)

### Community 71 - "Commercial Roadmap"
Cohesion: 0.24
Nodes (11): No priority score is computed, Assets held but unclaimed, The commercial roadmap, The forecast log (4c), From File to Product (artifact), Item 3: Scheduled delivery of the two views, Item 4: Durable sprint history (4a/4b/4c), Item 5: Permission mirroring (+3 more)

### Community 72 - "Jira Token Transport"
Cohesion: 0.18
Nodes (8): connect_jira(), need_requests(), The original path: a personal API token over HTTP basic auth. Still here, still…, Prove the connection is somebody, before a single figure is pulled. The check…, An OAuth grant if one is stored, otherwise the API token from the env. Which…, The dependency, or the sentence that says how to get it., _TokenTransport, _verified()

### Community 73 - "WASM Test Harness"
Cohesion: 0.18
Nodes (10): assets, cases, [casesPath, outPath, modeFlag], HERE, loadMs, require, results, runtime (+2 more)

### Community 74 - "Org Config Documentation"
Cohesion: 0.22
Nodes (9): The four flow tiles, statusTransitions sent raw by the resolver, A bad config stops the run, The config travels inside the data, orgConfig Jira project property on Forge, Organisation configuration (orgConfig), Two implementations, one behaviour, Holidays affect working days only (+1 more)

### Community 75 - "Manifest Wiring Tests"
Cohesion: 0.22
Nodes (10): _code_only(), _manifest_item(), The scalar fields of the manifest list item introduced by `- key: <key>`. Regex…, A scheduled trigger is not a resolver call, and the manifest said it was.…, A route is answered in-function or by the calculator, never both. The migration…, JavaScript with its comments stripped, so a check about what the code does is…, Sequencing and the forecast run as async events, and the page cannot tell. ADR…, test_routes_move_one_at_a_time() (+2 more)

### Community 76 - "Flow Tiles & No People Metrics"
Cohesion: 0.25
Nodes (9): Four flow tiles that need no sprint (1.17.0), Bundle, Cumulative flow, Cycle time percentile, Context (selected), ADR 0003: The dashboard does not measure people, No hours, overtime, timesheet field; no ranking of individuals, Team load: WIP and unplanned work from issue status (+1 more)

### Community 77 - "Refuse Rather Than Widen"
Cohesion: 0.28
Nodes (9): ADR 0007: Refuse rather than widen, Refusal clause: the evidence is absent, not noisy, Refuse rather than widen the interval, An empty selection is a refusal, not a zero, The disclosure must name the right cause, Refusal sentences are inserted verbatim, not passed through the model, Re-derivation is a labelled fallback, and disagreements are said aloud, A refusal is not a claim (+1 more)

### Community 78 - "Sample Bundle Generator"
Cohesion: 0.33
Nodes (8): build_history(), How many sprints of trend the dataset keeps. One reader, so the fetcher and…, Append this sprint to whatever history the previous file held, so the trend…, trend_window(), add_wd(), build(), main(), working_days()

### Community 79 - "Service Computes Nothing Tests"
Cohesion: 0.22
Nodes (9): call(), The service's answer is the tool's answer, to the byte., Intake's reference class, over the payload the calculator really receives.…, A different calendar is a different answer — including, sometimes, no answer., A traceback carries field values, and those are the customer's., test_config_travels_in_the_payload(), test_epic_sizing_survives_the_projection(), test_no_internals_leak() (+1 more)

### Community 80 - "Forge Deployment Guide"
Cohesion: 0.25
Nodes (8): Major vs minor Forge version rule, Finishing the Forge route, The registered app id never reaches HEAD, Shipping Forecast connection check admin page, After a scope change, reinstall — upgrade does not take, What lint will not tell you, asserted by tests/test_service.py, A negative result from synthetic input against an embedded frame is not evidence, The weekly brief scheduled trigger

### Community 81 - "Dashboard Review Notes"
Cohesion: 0.25
Nodes (8): Sprint 24 dashboard review, Burndown with a scope line and mid-sprint callout, Health score with the method exposed on hover, One completion figure from a single field, Predictability card with recommended next commitment, Waiting-vs-working elapsed time chart, Burndown carries both units, always, Commitment recommended at the 85%-confidence item count

### Community 82 - "Connection Probe"
Cohesion: 0.61
Nodes (7): call(), loadBoard(), main(), note(), show(), verdict(), withTimeout()

### Community 83 - "Demo Recording Script"
Cohesion: 0.39
Nodes (7): build_cards(), forecast_json(), main(), Opening and closing cards. The closing figures come from the real forecaster…, The closing card quotes the forecaster, so the numbers on it have to come from…, run(), scenes()

### Community 84 - "Candidate Asks Mirror"
Cohesion: 0.48
Nodes (7): asks_from_issues(), `(asks, notes)` — every declared candidate on this board, as asks. An ask has…, Candidacy is decided in the resolver, costing a JS mirror, asksFromIssues(), candidateAnswer(), candidateIssues(), tshirtAnswer()

### Community 85 - "Accessibility Suite"
Cohesion: 0.33
Nodes (5): Accessibility suite found 67 low-contrast nodes (1.7.0), UI colour tokens separate from chart palette, Every chart has a table view, check(), main()

### Community 86 - "Import Wizard Concepts"
Cohesion: 0.33
Nodes (7): Added-mid-sprint inferred from created date, All-numeric date disambiguation, Column mapping by synonym list, Import wizard (Load data), Burndown and history row recomputed on upload, Replace or merge apply modes, Load data modal (#modal), three steps

### Community 87 - "Plausible Wrong Number Class"
Cohesion: 0.33
Nodes (6): Flow-board forecast counted every issue three times (1.16.13), Jira's field list answers 200 anonymously (1.58.0), Migration to /rest/api/3/search/jql pages by token (1.56.0), Add the test before you claim the fix, The plausible wrong number failure class, Derived data is recomputed, never inherited

### Community 88 - "Forge Permissions"
Cohesion: 0.40
Nodes (5): editabilityFor(), ADMIN_PERMISSION, canAdminister(), editability(), ADR-0014

### Community 89 - "Window Forecast Tests"
Cohesion: 0.33
Nodes (6): A flow board's contexts and issues, one copy of the issue set per window. That…, The Monte Carlo tile, on a board whose contexts overlap. `team_slice()` gathers…, ADR 0011 has to hold in the forecaster as much as on the page. A window's…, test_a_window_is_not_a_deadline_to_the_forecaster(), test_the_forecaster_counts_one_issue_once(), _window_bundle()

### Community 90 - "Intake Demo Generator"
Cohesion: 0.60
Nodes (4): data/demo-intake-bundle.json, add_wd(), build(), main()

### Community 91 - "Weekly Brief Function"
Cohesion: 0.40
Nodes (5): Pyodide in the Custom UI iframe, unsafe-eval CSP option for WebAssembly, llm module brief-writer (claude), scheduledTrigger weekly-brief, function weekly-brief-fn (120 s, 1,024 MB)

### Community 92 - "Forecast Claims"
Cohesion: 0.50
Nodes (4): claim_id(), claims_from(), Deterministic, so re-publishing the same forecast does not duplicate it. A…, The falsifiable claims one published capacity forecast makes. `capacity` is…

### Community 93 - "Flow Time Glossary"
Cohesion: 0.67
Nodes (4): Cycle time, Flow efficiency, Lead time, Waiting

### Community 94 - "Issue Tracker & Labels"
Cohesion: 0.50
Nodes (4): Issue tracker: GitHub, GitHub issues on Xeno828/delivery-value-dashboard via gh, Triage labels, Five canonical triage labels

### Community 95 - "Recipient Validator Parity"
Cohesion: 0.50
Nodes (4): js_problems_for(), `problemsIn` from forge/src/recipients.js, over one config., `recipients.js` and `serve_live.recipient_problems` are one rule, twice. That…, test_the_two_recipient_validators_agree()

### Community 96 - "Two Transports Parity Test"
Cohesion: 0.50
Nodes (4): What `scripts/serve_live.py` really puts on the wire, for both routes. The…, One contract, two transports. The page reaches live mode either over a same-…, _serve_live_bodies(), test_the_two_transports_answer_the_same_shape()

### Community 97 - "Series Refusal Checks"
Cohesion: 0.50
Nodes (4): The durable sprint series — ADR 0015, roadmap item 4. Two halves, and the split…, Whether a route refused. Reported by exception type, not by grepping a sentence…, _refuses(), series_checks()

## Ambiguous Edges - Review These
- `size_stability()` → `size_stability(): the interchangeable-items assumption is checked`  [AMBIGUOUS]
  docs/adr/0006-forecast-in-items-not-points.md · relation: references
- `clean_dataset()` → `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md · relation: references
- `clean_dataset()` → `People picker searches by name, stores the id, projects to an allow-list of fields`  [AMBIGUOUS]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md · relation: semantically_similar_to

## Knowledge Gaps
- **329 isolated node(s):** `id`, `title`, `requestedBy`, `team`, `problemStatement` (+324 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 677 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `size_stability()` and `size_stability(): the interchangeable-items assumption is checked`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `clean_dataset()` and `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `clean_dataset()` and `People picker searches by name, stores the id, projects to an allow-list of fields`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **Why does `ADR 0008: Forge calls a hosted calculator` connect `Foundational ADRs` to `Calculator Service Routes`, `Facts Pack Metrics`, `Output Escaping & XSS`, `WebAssembly In-Function Runtime`, `Calculator Deploy & Provisioning`, `Dashboard Forecast Rendering`, `Monte Carlo Forecaster`, `ADR Index & Permission Records`, `Jira OAuth Login`, `Build & Security Suite`, `Forge Deployment Guide`, `Sequencing Without Scores`, `Async Jobs & No Arithmetic`, `Hosting & Realms`, `Live Mode Server`, `Scope Allow-list Tests`, `Intake Forecasting`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Why does `ADR 0009: One contract, two transports` connect `Bridge Adapter Transport` to `Foundational ADRs`, `Delivery Data Fetcher`, `WebAssembly In-Function Runtime`, `End-to-end Suite`, `Forge Context Parsing`, `Data Format & History Rows`, `ADR Index & Permission Records`, `Build & Security Suite`, `Forge Deployment Guide`, `Scope Allow-list Tests`, `Async Jobs & No Arithmetic`, `Empty Selection Refusals`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `ADR 0013: The brief is written inside the tenant` connect `Brief Delivery via Jira` to `Calculator Service Routes`, `Forge Resolver & Jira Reads`, `Foundational ADRs`, `Refuse Rather Than Widen`, `ADR Index & Permission Records`, `Forge Deployment Guide`, `Hosting & Realms`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **What connects `id`, `title`, `requestedBy` to the rest of the system?**
  _329 weakly-connected nodes found - possible documentation gaps or missing edges._