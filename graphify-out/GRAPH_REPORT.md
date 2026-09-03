# Graph Report - delivery-value-dashboard  (2026-09-03)

## Corpus Check
- 7 files · ~462,310 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1990 nodes · 3678 edges · 126 communities (101 shown, 23 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 157 edges (avg confidence: 0.86)
- Token cost: 344,756 input · 0 output

## Community Hubs (Navigation)
- Weekly Brief Composition
- Service Suite Checks
- Organisation Config Rules
- Forge Resolver & Runbook
- Forge Context & Audit Shapes
- Forge Async Jobs
- Jira Issue Normalisation
- Agent Tool Tests
- Import Wizard Screens
- Hosted Calculator (Retired)
- Root Package & Flow Glossary
- Jira OAuth Login
- Flow Boards & Config Refusals
- Dashboard Forecast Rendering
- Business Value & Roll-ups
- Roadmap & Permission ADRs
- Flow Board Changelog
- Security Suite
- Value & Candidate Fields
- Facts Pack Metrics
- Calculator Hosting History
- Refusals & Two Transports
- Founding ADRs & Badge
- Routes Projection & Refusals
- Dashboard Charts & Drilldowns
- Import Pipeline
- Forge Package Dependencies
- Intake Ask 030
- Runs on Atlassian Research
- Forecast Log & Claims
- Forecast Simulations
- Intake Tool Entry Points
- Delivery Data Fetcher
- Dashboard Screenshot
- WASM Parity & CI Suites
- Intake Ask 014
- Intake Ask 015
- Issue Selection & Slicing
- Forge Deployment History
- Weekly Brief History
- CLAUDE.md Constraints & ADR Index
- Agent Skill & Templates
- Refusal Thresholds
- Calculator Retirement (ADR 0031)
- Jira Client Fields
- Tile Picker & Presets
- Intake Ask 016
- Runtime Asset Packer
- Live Mode Server
- Live Jira Backend
- Dashboard Context Loading
- Demo & Burndown Scripts
- Page Workflow & Windows
- Brief Access & Permission ADRs
- In-function Python Runtime
- Durable Series History
- CI & Test Suites
- Intake Readiness & Capacity
- Forecast Build & Refusals
- Jira Pull & Value Fetch
- README & Agent Principles
- Page Constraints & Contributing
- Context Picker Screenshot
- Architecture & One Implementation
- Sequencing Without Scores
- Page Rendering Core
- Manifest & Jobs Tests
- Metrics & Runtime Bundle
- WASM Test Harness
- Forecast Tile & Agent
- Dashboard Review & No People Metrics
- Data Format & Dashboard Review
- Bridge Adapter & Jobs
- Contexts & Live Mode Docs
- Bundle Backend
- Live Series Server
- Service Computes Nothing Tests
- Candidate Asks Mirror
- History Rows
- Simulation Jobs
- Issue Normalisation & Escaping
- Intake Glossary
- Sequencing Route
- Page Shell & Tile Cards
- Build Script & Pages
- Intake Capacity Model
- Import Wizard Concepts
- Jira Token Transport
- Sample Bundle & History Rows
- Epic Sizing Ladder
- Window Forecaster Tests
- Items Not Points Glossary
- Team Load Glossary
- Intake Demo Generator
- Demo Bundle Generator
- Series Merge
- Import Date Parsing
- Recipient Validators
- Two Transports Test
- Series Checks
- Cross-team Roll-up
- Upload Pipeline
- Basis-count Fixes
- Ask Text Guard
- Queue Cost Scenarios
- Iframe Pyodide Option
- Refresh Script
- Recipient Names
- Recipient Edit View
- Read-only Recipients
- Item Counts Unit
- Forecast Log
- Issue-type Filter
- Ageing
- Risk Register
- Scope Growth
- Value Basis
- Intake Reproducibility
- Intake Blind Spots
- Pinned Residency
- Recipients Module
- E2E Suite
- Forge Shapes Harness
- Agent Suite

## God Nodes (most connected - your core abstractions)
1. `CLAUDE.md working constraints` - 61 edges
2. `check()` - 48 edges
3. `render()` - 42 edges
4. `ADR 0031 — The forecast runs inside the Forge function, and the calculator is retired` - 39 edges
5. `Decision records index` - 34 edges
6. `Hosting the calculator (retired 2026-09-03)` - 29 edges
7. `check()` - 28 edges
8. `ADR 0008: If we ship on Forge, Forge calls a hosted calculator` - 25 edges
9. `build()` - 21 edges
10. `sequence()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `People picker searches by name, stores the id, projects to an allow-list of fields` --semantically_similar_to--> `clean_dataset()`  [AMBIGUOUS] [semantically similar]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md → service/routes.py
- `Commitment recommendation` --references--> `recommend_commitment()`  [INFERRED]
  CONTEXT.md → agent/tools/forecast.py
- `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)` --references--> `clean_dataset()`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md → service/routes.py
- `Size stability` --references--> `size_stability()`  [INFERRED]
  CONTEXT.md → agent/tools/forecast.py
- `size_stability(): the interchangeable-items assumption is checked` --references--> `size_stability()`  [AMBIGUOUS]
  docs/adr/0006-forecast-in-items-not-points.md → agent/tools/forecast.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Dashboard header strip** — docs_screenshots_context_picker_header_line, docs_screenshots_context_picker_sprint_goal, docs_screenshots_context_picker_data_bundle_pill, docs_screenshots_context_picker_sprint_health_pill, docs_screenshots_context_picker_toolbar_actions [EXTRACTED 1.00]
- **CSV import wizard: upload, check column mapping, load** — docs_screenshots_import_mapping_upload_a_file_tab, docs_screenshots_import_mapping_step_2_of_3_check_column_mapping, docs_screenshots_import_mapping_column_mapping_table, docs_screenshots_import_mapping_jira_export_csv [EXTRACTED 1.00]
- **Created, started and resolved dates drive lead time, cycle time and burndown** — docs_screenshots_import_mapping_created_date_field, docs_screenshots_import_mapping_started_date_field, docs_screenshots_import_mapping_resolved_date_field, docs_screenshots_import_mapping_lead_time_metric, docs_screenshots_import_mapping_cycle_time_metric, docs_screenshots_import_mapping_burndown_metric [EXTRACTED 1.00]
- **Import wizard step 3: review counts, warnings and preview rows before applying** — docs_screenshots_import_preview_step_3_check_before_applying, docs_screenshots_import_preview_summary_tiles, docs_screenshots_import_preview_no_business_value_warning, docs_screenshots_import_preview_preview_table, docs_screenshots_import_preview_apply_to_the_dashboard [EXTRACTED 1.00]
- **Three ways in: upload a file, connect Jira/Asana, read the data format** — docs_screenshots_import_mapping_upload_a_file_tab, docs_screenshots_import_mapping_connect_jira_asana_tab, docs_screenshots_import_mapping_data_format_tab [EXTRACTED 1.00]
- **Refusal family: below the evidence, say the evidence is absent rather than print a plausible figure** — docs_adr_0007_refuse_rather_than_widen_refuse_rather_than_widen, docs_adr_0007_refuse_rather_than_widen_evidence_absent_not_noisy, docs_adr_0010_an_empty_selection_is_a_refusal_empty_selection_refusal, docs_adr_0011_a_kanban_context_is_a_window_not_a_clock_window_not_a_clock, docs_adr_0013_the_brief_is_written_inside_the_tenant_refusals_not_passed_through_model, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_refusal_not_a_claim [EXTRACTED 1.00]
- **Roadmap item 5: permission mirroring, its three exposures and their accepted answers** — docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_permission_mirroring_by_asuser, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_three_exposures, docs_adr_0019_a_recorded_row_is_a_fact_about_the_board_row_belongs_to_board, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_anchor_issue_access_control, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_restrict_browse, docs_adr_0013_the_brief_is_written_inside_the_tenant_asapp_reversal, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_offline_user_impersonation_deferred [EXTRACTED 1.00]
- **Flow charts: burndown, cycle time with waiting, work item age** — docs_screenshots_dashboard_burndown_with_scope_changes, docs_screenshots_dashboard_cycle_time_waiting_chart, docs_screenshots_dashboard_work_item_age [INFERRED 0.75]
- **Allow-list projection: stores and payloads hold named fields only, never issue text or contact details** — docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_scope_allow_list, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_people_picker_allow_list, docs_adr_0015_a_durable_series_stores_what_jira_forgets_counts_never_issue_text, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_claim_fields_allow_list, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_app_store_inventory, docs_adr_0021_the_audit_log_is_operational_and_says_so_audit_entry_allow_list [INFERRED 0.85]
- **Source > Project > Board > Sprint selection cascade** — docs_screenshots_context_picker_source_badge, docs_screenshots_context_picker_project_selector, docs_screenshots_context_picker_board_selector, docs_screenshots_context_picker_sprint_selector [INFERRED 0.85]
- **Decisions driven by the credible-wrong-number failure class** — docs_adr_0023_a_cross_team_rollup_spans_what_the_reader_can_see_rollup_does_not_forecast, docs_adr_0024_a_parent_and_its_subtasks_are_one_piece_of_work_count_subtasks, docs_adr_0026_items_and_value_are_counted_from_two_different_sets_two_sets_items_and_value, docs_forecasting_agent_reporting_scope_is_not_forecasting_scope [INFERRED 0.85]
- **Narrative panel, KPI tiles and risk list are three views of the same sprint facts** — docs_screenshots_dashboard_what_this_sprint_means, docs_screenshots_dashboard_kpi_tiles, docs_screenshots_dashboard_risks_and_what_to_do [INFERRED 0.85]
- **The async job path: resolver pushes, consumer computes, adapter polls** — forge_manifest_function_simulation_fn, forge_manifest_consumer_simulation_consumer, forge_src_jobs, docs_adr_0031_the_forecast_runs_inside_the_forge_function_job_row, docs_adr_0031_the_forecast_runs_inside_the_forge_function_retry_guard, forge_bridge_bridge, docs_adr_0031_the_forecast_runs_inside_the_forge_function_payload_chunks_in_app_storage [INFERRED 0.85]
- **One implementation of every figure, held by byte-for-byte parity** — claude_agent_never_does_arithmetic, claude_nothing_between_tools_and_reader_does_arithmetic, docs_adr_0031_the_forecast_runs_inside_the_forge_function_one_implementation_of_every_figure, service_readme_routes_compute_nothing, tests_test_wasm, tests_test_service, docs_adr_0005_tools_compute_the_agent_narrates [INFERRED 0.85]
- **Pyodide-in-function route: research, probes, manifest functions** — docs_research_2026_09_01_runs_on_atlassian_badge_pyodide_in_forge_function, docs_research_2026_09_02_second_probe_consumer_and_snapshot_wasm_probe_2, docs_research_2026_09_01_forge_async_events_consumer_module [INFERRED 0.95]
- **ADR 0031: Forge in-function WebAssembly migration** — docs_adr_0031_the_forecast_runs_inside_the_forge_function_record, service_routes_py_module, forge_src_runtime_js_module, forge_build_assets_mjs_module, forge_src_jobs_js_module, tests_test_wasm_py_module, changelog_v1_76_0, changelog_v1_78_0 [EXTRACTED 0.90]
- **No-priority-score family of decisions** — docs_adr_0004_no_priority_score_record, docs_adr_0027_a_value_basis_is_prose_carried_to_a_reader_record, docs_adr_0028_candidacy_is_a_state_somebody_declares_record, docs_adr_0029_a_t_shirt_band_selects_a_reference_class_record [INFERRED 0.85]
- **Roadmap item 5: permission-mirroring and disclosure ADRs** — docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_record, docs_adr_0019_a_recorded_row_is_a_fact_about_the_board_record, docs_adr_0015_a_durable_series_stores_what_jira_forgets_record, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_record, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_record, docs_adr_0021_the_audit_log_is_operational_and_says_so_record [EXTRACTED 0.90]

## Communities (126 total, 23 thin omitted)

### Community 0 - "Weekly Brief Composition"
Cohesion: 0.06
Nodes (63): ADR-0005, ADR-0007, ADR-0014, People picker searches by name, stores the id, projects to an allow-list of fields, briefMessages(), composeBrief(), contentText(), DECLINED (+55 more)

### Community 1 - "Service Suite Checks"
Cohesion: 0.05
Nodes (64): A sixth suite: Pyodide answer equals native byte for byte, ask_assembly_checks(), audit_log_checks(), body_keys_reach_a_reader(), business_value_checks(), check(), counting_checks(), cross_team_checks() (+56 more)

### Community 2 - "Organisation Config Rules"
Cohesion: 0.06
Nodes (49): meta.calendar must equal inputs.calendar, add_working_days(), candidate_answer(), candidate_issues(), counted_issues(), counted_note(), from_dataset(), holiday_set() (+41 more)

### Community 3 - "Forge Resolver & Runbook"
Cohesion: 0.07
Nodes (40): ADR-0008, ADR-0009, ADR-0013, invokeRemote() from @forge/api, forge/src/compose.js keeps the send provable without deploying, answerHere(), appFieldsFor(), ASK_TEXT_FIELDS (+32 more)

### Community 4 - "Forge Context & Audit Shapes"
Cohesion: 0.06
Nodes (50): ADR-0015, ADR-0021, ADR-0028, problemsInAuditEntry: counts, flags, field names, one actor identity, appendAudit(), AUDIT_EVENTS, AUDIT_FIELDS, AUDIT_KEY (+42 more)

### Community 5 - "Forge Async Jobs"
Cohesion: 0.07
Nodes (46): ADR-0017, ADR-0018, chunkPayload(), collect(), CONSUMER_ROUTES, FAILED_SENTENCE, failedSentence(), forecastRefusal() (+38 more)

### Community 6 - "Jira Issue Normalisation"
Cohesion: 0.05
Nodes (47): ADR-0011, ADR-0024, ADR-0025, ADR-0026, ADR-0027, ADR-0029, No text from the page reaches Jira, Business Value custom field (jira:customField) (+39 more)

### Community 7 - "Agent Tool Tests"
Cohesion: 0.07
Nodes (47): check(), _intake_ds(), near(), An unauthenticated pull must stop, not degrade — found against live Jira.…, The facts pack reports the sprint; the forecaster uses all history. Conflating…, `/rest/api/3/search` was removed; `/search/jql` pages by token. Not a URL swap.…, The three ways a forecast can be built from the wrong slice of the file. All…, The headline output: is the range driven by not knowing the size, or by normal… (+39 more)

### Community 8 - "Import Wizard Screens"
Cohesion: 0.06
Nodes (42): Import mapping screenshot, Assignee field, Auto-detected mapping (green check status), Burndown and completion, Column mapping table (Dashboard field / Your column / Example value / Status), Connect Jira / Asana tab, Created date field (drives ageing and lead time), Custom field mapping (story points, started date) (+34 more)

### Community 9 - "Hosted Calculator (Retired)"
Cohesion: 0.06
Nodes (40): New module type or scope change is major; another entry under a declared block is not, No silent caps, Region pinning resolved by Forge per install, Rejected: an IP allow-list as access control, ADR 0016: The image takes Debian's security updates at build time, The image applies Debian security updates at build time, Distroless is not a minimal CVE surface for Python, Scan gate: fixable HIGH/CRITICAL block; unfixable are reported (+32 more)

### Community 10 - "Root Package & Flow Glossary"
Cohesion: 0.06
Nodes (35): Board, Bundle, Cumulative flow, Cycle time, Flow board, Flow health, Health score, Lead time (+27 more)

### Community 11 - "Jira OAuth Login"
Cohesion: 0.10
Nodes (25): The personal API token path lives only in scripts/, Connecting Jira and Asana, Fetcher with an API token (scripts/fetch_delivery_data.py), MCP connectors and CSV export routes, OAuth 2.0 (3LO) route via scripts/jira_auth.py, OAuth 2.0 (3LO) for a Jira that is not your own, accessible_resources(), authorize_url() (+17 more)

### Community 12 - "Flow Boards & Config Refusals"
Cohesion: 0.08
Nodes (34): Flow board window context (kind: window), Flow health composite, Sprint health refuses whole on a flow board, Refuse in place versus not shown, statusTransitions sent raw by the resolver, A bad config stops the run, The config travels inside the data, orgConfig Jira project property on Forge (+26 more)

### Community 13 - "Dashboard Forecast Rendering"
Cohesion: 0.10
Nodes (29): ADR-0004, ADR-0023, auditHtml(), bindForecastInputs(), briefAudienceFields(), briefBoard(), briefList(), fcKey() (+21 more)

### Community 14 - "Business Value & Roll-ups"
Cohesion: 0.09
Nodes (33): One issue's business value as it should be counted, or zero. The one place the…, value_of(), Business value counted at one hierarchy level, ADR 0004: Intake returns delivery consequence, never a priority score, Delivery consequence of an ordering, No WSJF or value-over-effort priority score, ADR 0023 Cross-team roll-up spans what the reader can see, Cross-team roll-up (+25 more)

### Community 15 - "Roadmap & Permission ADRs"
Cohesion: 0.12
Nodes (31): Score past forecasts against what actually happened. Without this the agent is…, score_calibration(), Calibration, Durable series, Reconstructed row, Recorded row, The disclosure must name the right cause, ADR 0015: A durable series stores what Jira forgets, and re-derivation is a labelled fallback (+23 more)

### Community 16 - "Flow Board Changelog"
Cohesion: 0.08
Nodes (29): agent/tools/orgconfig.py, v1.14.0 OAuth 2.0 3LO connection and orgConfig, v1.16.1 Empty sprint scored 66/100 bug; ADR 0010 written, v1.16.11 Flow board hides inapplicable sprint tiles, v1.16.2 Missing calendar scored as bad delivery bug, v1.16.4 Sprint-length fallback bug; ADR 0011 written, v1.16.6 Flow-board windows offered and loaded, v1.16.7 Window is not a clock enforced on page (+21 more)

### Community 17 - "Security Suite"
Cohesion: 0.15
Nodes (26): Credentials live only in the fetcher's environment, Threat model: the file gets emailed, Single self-contained HTML file, Forge CSP forbids inline style/script; split build and CSSOM setter wrap, No Atlassian credential, session or auth module in the app, SSO is inherited because the app owns no identity, requests>=2.31 (fetcher's only dependency), browser_checks() (+18 more)

### Community 18 - "Value & Candidate Fields"
Cohesion: 0.14
Nodes (26): agent/tools/intake.py, v1.48.0 Activity log built, v1.54.0 Business Value field declared, v1.57.0 Value Basis field declared, v1.57.1 Value Basis version-cost correction, v1.63.0 Candidate field declared, v1.65.0 Declared candidate becomes an ask, v1.67.0 Value and basis shown on sequencing tile (+18 more)

### Community 19 - "Facts Pack Metrics"
Cohesion: 0.11
Nodes (25): burndown(), _d(), diff(), elapsed_days(), facts(), _get(), in_sprint(), is_done() (+17 more)

### Community 20 - "Calculator Hosting History"
Cohesion: 0.11
Nodes (26): agent/tools/selection.py, v1.19.0 invokeRemote wired; nested-claim bug fixed (ADR 0012), v1.20.0 Cloud Run provisioning wizard and CI deploy, v1.20.2 Trailing-newline shared-secret bug fixed, v1.21.0 Calculator tenant-aware in production, v1.22.0 selection.py slice logic centralised, v1.69.1 Value tile stops guessing reasons, v1.73.0 Hostnames and realms committed once (+18 more)

### Community 21 - "Refusals & Two Transports"
Cohesion: 0.10
Nodes (26): An empty selection is a refusal, not a zero, Live mode has two transports and one set of body shapes, Live mode, ADR 0007: Below the evidence thresholds, refuse rather than widen the interval, Refusal clause: the evidence is absent, not noisy, Refuse rather than widen the interval, ADR 0009: One contract, two transports, Forge bridge adapter (window.__DVD_BRIDGE__) (+18 more)

### Community 22 - "Founding ADRs & Badge"
Cohesion: 0.13
Nodes (26): ADR 0001: The dashboard is one self-contained HTML file, ADR 0005: The tools compute; the agent only narrates, Tools compute; the agent narrates, ADR 0008: If we ship on Forge, Forge calls a hosted calculator, Hosted calculator imports the Python tools unchanged, Pyodide (CPython under WebAssembly) inside the Forge function, Pyodide in the Custom UI iframe (rejected), Runs on Atlassian badge (+18 more)

### Community 23 - "Routes Projection & Refusals"
Cohesion: 0.16
Nodes (24): Exception, check_sequence(), clean_dataset(), _clean_issue(), _iso_or_none(), A bad request, with the sentence to send back., The dataset the tools will see, or a refusal saying what was wrong., Which contexts a forecast for this one would sample. The caller that needs this… (+16 more)

### Community 24 - "Dashboard Charts & Drilldowns"
Cohesion: 0.19
Nodes (25): Drill-down, Adding a metric, cycleRows(), drawTable(), littlesLaw(), openDrill(), pctile(), renderAge() (+17 more)

### Community 25 - "Import Pipeline"
Cohesion: 0.15
Nodes (20): Import problem issue template, assemble(), autoMap(), buildBurndown(), buildHistoryRow(), buildIssues(), detectOrder(), drawMapTable() (+12 more)

### Community 26 - "Forge Package Dependencies"
Cohesion: 0.08
Nodes (23): esbuild, @forge/api, @forge/bridge, @forge/events, @forge/kvs, @forge/llm, dependencies, @forge/api (+15 more)

### Community 27 - "Intake Ask 030"
Cohesion: 0.09
Nodes (22): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+14 more)

### Community 28 - "Runs on Atlassian Research"
Cohesion: 0.10
Nodes (23): Async event at-least-once delivery and retries, Consumer function limits: 900 s, 1,024 MB, Forge consumer module, Forge Realtime as an alternative to polling, Job status is counts only; cancel exists, KVS as the result store for a poller, Documented major-version change list, Research note: async events for sequencing (2026-09-01) (+15 more)

### Community 29 - "Forecast Log & Claims"
Cohesion: 0.12
Nodes (21): calibration_note(), claim_id(), claims_from(), _narrow_sentence(), problems_in_claim(), Deterministic, so re-publishing the same forecast does not duplicate it. A…, The falsifiable claims one published capacity forecast makes. `capacity` is…, What is wrong with one logged claim, as sentences. Empty means storable.… (+13 more)

### Community 30 - "Forecast Simulations"
Cohesion: 0.13
Nodes (22): add_working_days(), CountForecast, cycle_times(), _d(), DateForecast, forecast_completion(), forecast_count_by_date(), full_history_days() (+14 more)

### Community 31 - "Intake Tool Entry Points"
Cohesion: 0.18
Nodes (20): attribute_uncertainty(), board_issues(), _fmt(), _fmt_sequence(), forecast_ask(), main(), _pct(), Every issue belonging to one board, across every sprint in the file. (+12 more)

### Community 32 - "Delivery Data Fetcher"
Cohesion: 0.16
Nodes (21): Started date lives in the changelog, not the export, asana_pull(), build_burndown(), configure(), connect_jira(), d(), jira_bundle(), jira_pull() (+13 more)

### Community 33 - "Dashboard Screenshot"
Cohesion: 0.11
Nodes (22): Dashboard screenshot (Sprint 24 — delivery and value), Burndown with scope changes shown, Business value delivered ($34,800 estimated, with stated basis), Can we trust the forecast? (committed vs completed, last six sprints), How long work takes and how much is waiting (flow efficiency per closed item), Every figure traces back to an issue (footer principle, click-through links), Filter row (Source, Project, Board, Sprint, Person, Epic, Type, Status, Find), Flow efficiency (32% of elapsed time was active work) (+14 more)

### Community 34 - "WASM Parity & CI Suites"
Cohesion: 0.16
Nodes (21): _intake_bodies(), project(), The measurement the architecture is built on, asserted rather than recalled.…, The service's answer is the tool's answer, to the byte., The demo intake bundle, projected, and its asks stripped of every word. What…, A different calendar is a different answer — including, sometimes, no answer., One team's slice, projected — exactly what the Forge resolver sends., team_payload() (+13 more)

### Community 35 - "Intake Ask 014"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 36 - "Intake Ask 015"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 37 - "Issue Selection & Slicing"
Cohesion: 0.15
Nodes (18): cross_team_boards(), cross_team_label(), cross_team_members(), forecast_for(), Which issues a forecast reads, and what it is told about them. This is the…, The context a forecast is *for*, and the sprints a rollup stands for. Returns…, Which contexts a forecast for `cid` would sample, and how it chose them.…, Run the real forecaster for one context. Returns None for an unknown id. The… (+10 more)

### Community 38 - "Forge Deployment History"
Cohesion: 0.13
Nodes (19): v1.15.0 Decision: host Python as a calculator (ADR 0008), v1.18.0 Forge-token auth mode written, v1.23.1 Real Atlassian invocation token accepted, v1.29.1 Scheduled trigger proved; iframe clip found, v1.29.5 No bug: Forge iframe scrolls with a mouse, v1.39.0 Debian security-update build fix (ADR 0016), v1.64.0 Forge CSP dropped inline style attributes, v1.72.3 Stale deployment-status prose fixed (+11 more)

### Community 39 - "Weekly Brief History"
Cohesion: 0.15
Nodes (20): v1.23.0 Forecast wired to hosted calculator, v1.25.0 llm module declared; trigger handler fixed, v1.25.1 llm module deployed; wrong diagnosis published, v1.26.0 Jira sends the brief (ADR 0014), v1.27.0 Brief email rendering and send written, v1.29.0 Scheduled brief reads board and sends, v1.30.0 Item 3 runs end to end; six failures fixed, v1.31.0 Recipient picker takes a name (+12 more)

### Community 40 - "CLAUDE.md Constraints & ADR Index"
Cohesion: 0.12
Nodes (20): CLAUDE.md working constraints, dist/ is committed on purpose, Monte Carlo is seeded and reproducible, Never compute a priority score, No hours, overtime, or timesheet field, Every Forge scope is read-only except two named ones, When you change something, Zero-throughput days stay in the sample (+12 more)

### Community 41 - "Agent Skill & Templates"
Cohesion: 0.15
Nodes (19): Sprint 24 delivery brief (worked example), Sprint 24 team report (worked example), delivery-report agent skill, Evidence tagging, Prohibited outputs, Agent refusal thresholds, Agent sequence: load, diff, forecast, reconcile, write, log, score, Exec brief template (+11 more)

### Community 42 - "Refusal Thresholds"
Cohesion: 0.12
Nodes (19): Is item-count forecasting still safe for this team? Counting items assumes…, size_stability(), Refusal thresholds are hard, not advisory, Size stability, ADR 0006: Forecasts count items, never story points, Forecasts count items, never story points, size_stability(): the interchangeable-items assumption is checked, Published calibration score that stops probabilities (+11 more)

### Community 43 - "Calculator Retirement (ADR 0031)"
Cohesion: 0.11
Nodes (19): The manifest declares no remote and must not gain one, Calculator, ADR 0031 — The forecast runs inside the Forge function, and the calculator is retired, Budget: 900 seconds and 1,024 MB, The event carries the projection, Resolver loads from a memory snapshot; the consumer does not, Forecast payload travels through app storage in chunks, Rejected: committing the generated runtime module (+11 more)

### Community 44 - "Jira Client Fields"
Cohesion: 0.15
Nodes (9): Jira, The Jira surface this script needs, over either transport. `url` is the…, Who this connection is authenticated as — `(identity, None)`, or `(None, why)`…, Locate the story-point and sprint custom fields by display name., The field that says an issue is an ask — ours, or the site's own. `"app"` is…, The field carrying an ask's t-shirt band — ours, or the site's own. Same rule…, This app's own Business Value and Value Basis fields on this site. **Matched on…, The board's epics as issues — ADR 0026. **Epics are not on a scrum board.**… (+1 more)

### Community 45 - "Tile Picker & Presets"
Cohesion: 0.18
Nodes (19): announcePicker(), applyOrder(), applyTiles(), buildPicker(), buildPickerList(), download(), focusMover(), moveTile() (+11 more)

### Community 46 - "Intake Ask 016"
Cohesion: 0.11
Nodes (17): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+9 more)

### Community 47 - "Runtime Asset Packer"
Cohesion: 0.11
Nodes (16): Generated at deploy, never committed, { BOOT, writeSources }, digest, files, hash, HERE, OUT, probe (+8 more)

### Community 48 - "Live Mode Server"
Cohesion: 0.19
Nodes (13): append_audit(), Handler, A mirror of `problemsIn` in forge/src/recipients.js, in Python. A second…, One board's forecast log. Missing and unreadable both read as empty — a caller…, Mirrors `appendAudit` in forge/src/audit.js, bound included. Best-effort and…, The one route that changes something. A POST rather than a GET with parameters,…, read_audit(), read_forecast_log() (+5 more)

### Community 49 - "Live Jira Backend"
Cohesion: 0.14
Nodes (11): JiraBackend, The third part of a flow board's context id. Prefixed rather than bare, so a…, Which issues are *in* a window, as a JQL predicate. The membership ADR 0011…, One selectable window, in the shape the sprint entry above uses. Field for…, Queries Jira on demand. Sprint lists are cheap; issues are fetched only when a…, The saved filter behind a board, which is how plain JQL is scoped to one. The…, Sequencing sizes asks against the board's completed epics and its interruption…, Unlike the bundle, this has to fetch. A forecast needs the team's whole… (+3 more)

### Community 50 - "Dashboard Context Loading"
Cohesion: 0.17
Nodes (18): fetchSeries(), filtered(), loadContext(), loadRollupMembers(), orgConfigOf(), orgSummary(), probeLive(), refreshLive() (+10 more)

### Community 51 - "Demo & Burndown Scripts"
Cohesion: 0.20
Nodes (14): Repository layout, _d(), in_sprint(), main(), Same rule as the facts pack: in scope unless finished before the start., rebuild(), working_days(), build_cards() (+6 more)

### Community 52 - "Page Workflow & Windows"
Cohesion: 0.19
Nodes (16): applyWorkflow(), boardStatuses(), buildView(), contextWorkingDays(), inferredSentence(), inferredStatuses(), isWindow(), M_FLOW() (+8 more)

### Community 53 - "Brief Access & Permission ADRs"
Cohesion: 0.20
Nodes (15): ADR 0013: The brief is written inside the tenant; only the file leaves, Superseded in part: the scheduled read takes asApp() deliberately, The file leaves: mailing is the one boundary crossing (later closed by ADR 0014), The brief is written by Forge LLMs in Atlassian's runtime, A scheduled trigger runs with no user principal, ADR 0014: Jira sends the brief, and the read-only rule bends by allow-list, Jira sends the brief via issue notify; nothing leaves, Outgoing mail is a site setting, not a scope (+7 more)

### Community 54 - "In-function Python Runtime"
Cohesion: 0.21
Nodes (13): How the runtime travels, answer(), baseDir(), fs, load(), loadAssets(), os, path (+5 more)

### Community 55 - "Durable Series History"
Cohesion: 0.20
Nodes (14): v1.36.0 history_row unified; ADR 0015 written, v1.37.0 series.js durable-series module, v1.40.2 Roadmap item 4 lettering corrected, v1.41.0 Calibration scoring implemented, v1.43.0 Trend window made a setting, v1.44.0 Permission mirroring exposures surveyed, v1.45.0 Recorded row is board's, permission rules, v1.46.0 Forecast log resolution gates (+6 more)

### Community 56 - "CI & Test Suites"
Cohesion: 0.18
Nodes (10): CI build & test workflow, dist/ staleness check, Actions pinned to majors, WebAssembly parity CI step, The suites CI enforces, Security & accessibility are tested, not asserted, check(), main() (+2 more)

### Community 57 - "Intake Readiness & Capacity"
Cohesion: 0.18
Nodes (13): Intake mode, Intake brief template, readiness(), Capacity scenario, Cost of the queue, Queue ahead, Readiness, Uncertainty attribution (+5 more)

### Community 58 - "Forecast Build & Refusals"
Cohesion: 0.21
Nodes (12): build(), main(), Historical mid-sprint scope growth, as a multiplier per period. Needs the…, How many items can this team commit to in a sprint, and at what confidence?…, Returned instead of a forecast when the data cannot support one. The agent must…, window_days=None means every day of imported history, which is the default here…, recommend_commitment(), Refusal (+4 more)

### Community 59 - "Jira Pull & Value Fetch"
Cohesion: 0.15
Nodes (13): v1.24.0 Roadmap committed; Forge LLMs chosen (ADR 0013), v1.32.0 Brief delivered; item 3 done; name search, v1.55.0 Epics fetched separately for value, v1.55.0 negative-count value-tile bug fixed, v1.56.0 Jira search API migration to /search/jql, v1.56.1 ADR 0026 written retroactively, v1.58.0 First real Jira pull; anonymous-field bug, v1.58.1 Accepted status stated not inferred (+5 more)

### Community 60 - "README & Agent Principles"
Cohesion: 0.15
Nodes (12): The agent never does arithmetic, Deploying: email, shared drive, Pages, board pack, Fetcher script for regular refreshes, The four questions activity reporting fails to answer, MCP connectors once the format has proved itself, Monte Carlo forecasting in the page, The reporting & forecasting agent, Sequence asks mode (+4 more)

### Community 61 - "Page Constraints & Contributing"
Cohesion: 0.17
Nodes (12): UI colour tokens are separate from the chart palette, Built file makes zero network calls and uses zero browser storage, Charts follow the colour rules, Derived data is recomputed, never inherited, Every chart has a table view, Every number traces to issues, No browser storage, No bundler, no npm install, no transpile (+4 more)

### Community 62 - "Context Picker Screenshot"
Cohesion: 0.22
Nodes (13): Context picker screenshot, Board selector, Context bar (Source / Project / Board / Sprint), Data-as-at timestamp, Data bundle pill (Demo bundle - 3 boards x 6 sprints), Header line (Project · Team · Sprint dates · data as at), Project selector, Source badge (JIRA) (+5 more)

### Community 63 - "Architecture & One Implementation"
Cohesion: 0.17
Nodes (12): agent/SKILL.md, Architecture in one paragraph, Nothing between the tools and a reader may do arithmetic, One implementation of every figure, Agent intake mode's four standing rules, Uncertainty attribution (size vs delivery), service/ README, The directory is named for what used to be beside routes.py (+4 more)

### Community 64 - "Sequencing Without Scores"
Cohesion: 0.20
Nodes (12): The refusal sentence for more asks than one sequencing compares, or None. A…, For a set of asks against one team, what each ordering costs the others.…, sequence(), too_many_asks(), A value basis is prose, never an input, Value figure as a floor with a basis line per item, Sequencing returns consequences, never a score, At most twelve asks on every transport (+4 more)

### Community 65 - "Page Rendering Core"
Cohesion: 0.20
Nodes (12): commitU(), contextById(), derive(), renderExec(), renderHeader(), renderKpis(), renderRisk(), rollupCovers() (+4 more)

### Community 66 - "Manifest & Jobs Tests"
Cohesion: 0.18
Nodes (12): _code_only(), _manifest_item(), The scalar fields of the manifest list item introduced by `- key: <key>`. Regex…, A scheduled trigger is not a resolver call, and the manifest said it was.…, Every route `index.js` answers is in the written inventory, and vice versa. The…, esbuild bundles an undefined identifier without a word. `answerHere` was lost…, JavaScript with its comments stripped, so a check about what the code does is…, Sequencing and the forecast run as async events, and the page cannot tell. ADR… (+4 more)

### Community 67 - "Metrics & Runtime Bundle"
Cohesion: 0.27
Nodes (11): agent/tools/metrics.py, v1.17.0 Four flow tiles added, v1.72.0 Burndown answered on Forge for first time, v1.72.1 Burndown date/string type bug, v1.76.1 Python runtime bundled for Forge, v1.76.2 WASM parity suite (test_wasm.py), ADR 0003 Dashboard Does Not Measure People, forge/build-assets.mjs (+3 more)

### Community 68 - "WASM Test Harness"
Cohesion: 0.18
Nodes (10): assets, cases, [casesPath, outPath, modeFlag], HERE, loadMs, require, results, runtime (+2 more)

### Community 69 - "Forecast Tile & Agent"
Cohesion: 0.22
Nodes (10): agent/SKILL.md, agent/tools/forecast.py, v1.10.0 Monte Carlo forecast tile on dashboard, v1.16.13 Flow-board forecast 2.5x-too-fast bug fixed, v1.28.0 Per-board recipients tile added, v1.2.0 Forecasting agent added, v1.71.0 Value-window exclusion and refusal-arithmetic bugs, v1.72.2 Future-sprint burndown mislabeled (+2 more)

### Community 70 - "Dashboard Review & No People Metrics"
Cohesion: 0.22
Nodes (10): ADR 0003: The dashboard does not measure people, No hours, overtime, timesheet field; no ranking of individuals, Team load: WIP and unplanned work from issue status, Sprint 24 dashboard review, Health score with the method exposed on hover, One completion figure from a single field, Predictability card with recommended next commitment, Team load card replacing output-per-person and overtime (+2 more)

### Community 71 - "Data Format & Dashboard Review"
Cohesion: 0.20
Nodes (10): Context: one project + board + sprint, Burndown with a scope line and mid-sprint callout, Data format, Burndown carries both units, always, orgConfig.inferredStatuses, started, recovered from the changelog, Units: items by default; calendar days reported, working days simulated, Window context ids on flow boards (win:14d/30d/90d) (+2 more)

### Community 72 - "Bridge Adapter & Jobs"
Cohesion: 0.25
Nodes (6): ADR-0031, Item 1: OAuth app on the Marketplace — done, as both routes, ceilingBody(), collectJob(), JOB_ROUTES, POLL_INTERVALS_MS

### Community 73 - "Contexts & Live Mode Docs"
Cohesion: 0.22
Nodes (9): ADR 0002: The page never queries Jira or Asana; data arrives as a bundle, Contexts fetched up front into a bundle, Live mode: local server on 127.0.0.1, The page cannot call Jira or Asana itself, Filtering by project, board and sprint (contexts and live mode), Bundle format (schemaVersion 2.0), Live mode via scripts/serve_live.py, Interaction cost is flat in dataset size (+1 more)

### Community 74 - "Bundle Backend"
Cohesion: 0.22
Nodes (5): BundleBackend, main(), no_days_yet_note(), Why a sprint's chart has no day on it that has happened yet, or `None`. Mirrors…, Reads an existing bundle file. Used for demos, tests, and for working offline…

### Community 75 - "Live Series Server"
Cohesion: 0.22
Nodes (9): One board's recorded rows. Missing and unreadable both read as empty. Keyed by…, Whether this observation may be written. Mirrors `recordable` in…, The trend series for the board `cid` belongs to, and the recording of it. The…, Mirrors `statusFingerprint` in `forge/src/series.js`. Order- and case-…, read_series(), series_fingerprint(), series_for(), series_recordable() (+1 more)

### Community 76 - "Service Computes Nothing Tests"
Cohesion: 0.22
Nodes (9): call(), Intake's reference class, over the payload the calculator really receives.…, `service/` is `routes.py` and nothing else. ADR 0031. The hosted calculator's…, One route, answered: `(status, payload)`. The signature kept the shape of the…, A traceback carries field values, and those are the customer's., test_epic_sizing_survives_the_projection(), test_no_internals_leak(), test_refusals() (+1 more)

### Community 77 - "Candidate Asks Mirror"
Cohesion: 0.39
Nodes (8): asks_from_issues(), `(asks, notes)` — every declared candidate on this board, as asks. An ask has…, Candidacy is decided in the resolver, costing a JS mirror, reattach(), asksFromIssues(), candidateAnswer(), candidateIssues(), tshirtAnswer()

### Community 78 - "History Rows"
Cohesion: 0.25
Nodes (8): history_row(), history_series(), One sprint's row of the trend series, as it stood at `as_of`. **Every count…, One row per sprint context, in the order the board runs them. The loop lives…, First answer, corrected: wipItems re-derives correctly, History rows are derived from dates at asOfDate, never current status, build_history(), Append this sprint to whatever history the previous file held, so the trend…

### Community 79 - "Simulation Jobs"
Cohesion: 0.32
Nodes (8): v1.16.0 Forge tenant shows own Jira; ADR 0009 written, v1.77.0 Sequencing runs as a Forge job, v1.77.3 Forecast becomes an async job, forge/bridge/bridge.js, consumer simulation-consumer / simulations queue, function simulation-fn (simulationConsumer), forge/src/jobs.js, tests/jobs_shapes.mjs

### Community 80 - "Issue Normalisation & Escaping"
Cohesion: 0.29
Nodes (8): Escape at output, once, Escape at output, exactly once, issueRow(), normaliseIssue(), noteInferred(), safeUrl(), statusCategoryOf(), valueCounts()

### Community 81 - "Intake Glossary"
Cohesion: 0.29
Nodes (8): Ask, Band, Candidate, Epic, Reference class, Sequence, Sizing method, T-shirt scale

### Community 82 - "Sequencing Route"
Cohesion: 0.25
Nodes (7): What an ask is inside Jira (open product question), GET api/sequence?id=, Sequencing was blocked on what an ask is inside Jira, load_asks(), Every recorded ask for one board. Read per request rather than cached: an ask…, What each ordering of this board's outstanding asks costs the others. Same tool…, sequence_for()

### Community 83 - "Page Shell & Tile Cards"
Cohesion: 0.25
Nodes (8): The four flow tiles, Brief recipients card (#c-brief), Build placeholders @@STYLES@@ @@SEED@@ @@APP@@ @@IMPORT@@, Filter bar: person, epic, types, status, find, measure, Flow tile cards: c-cycle, c-wip, c-thr, c-cfd, Issue drill-down panel (#panel), Dashboard page shell (src/index.html), Tile grid (#grid)

### Community 84 - "Build Script & Pages"
Cohesion: 0.43
Nodes (6): GitHub Pages publish job, build(), build_split(), main(), The same sources as separate files, for a host that forbids inline assets. The…, Path

### Community 85 - "Intake Capacity Model"
Cohesion: 0.29
Nodes (7): capacity(), _d(), interruption_rate(), queue_ahead(), Share of each sprint that arrived after planning, averaged. Capacity available…, Items already committed and not finished — the work this ask sits behind. Mid-…, Throughput samples available to a new ask under one scenario.

### Community 86 - "Import Wizard Concepts"
Cohesion: 0.33
Nodes (7): Added-mid-sprint inferred from created date, All-numeric date disambiguation, Column mapping by synonym list, Import wizard (Load data), Burndown and history row recomputed on upload, Replace or merge apply modes, Load data modal (#modal), three steps

### Community 87 - "Jira Token Transport"
Cohesion: 0.29
Nodes (4): need_requests(), The original path: a personal API token over HTTP basic auth. Still here, still…, The dependency, or the sentence that says how to get it., _TokenTransport

### Community 88 - "Sample Bundle & History Rows"
Cohesion: 0.48
Nodes (6): How many sprints of trend the dataset keeps. One reader, so the fetcher and…, trend_window(), add_wd(), build(), main(), working_days()

### Community 89 - "Epic Sizing Ladder"
Cohesion: 0.33
Nodes (6): epic_sizes(), Item counts of *finished* epics on this board — the reference class. "Finished"…, Epic grouping field chosen once for the whole set, What counts as a finished epic, The sizing ladder (tshirt / reference-class / explicit), T-shirt sizes calibrated per board

### Community 90 - "Window Forecaster Tests"
Cohesion: 0.33
Nodes (6): A flow board's contexts and issues, one copy of the issue set per window. That…, The Monte Carlo tile, on a board whose contexts overlap. `team_slice()` gathers…, ADR 0011 has to hold in the forecaster as much as on the page. A window's…, test_a_window_is_not_a_deadline_to_the_forecaster(), test_the_forecaster_counts_one_issue_once(), _window_bundle()

### Community 91 - "Items Not Points Glossary"
Cohesion: 0.40
Nodes (5): Forecasting rules, Forecasts are in items, never story points, Issue, Item, Point

### Community 92 - "Team Load Glossary"
Cohesion: 0.40
Nodes (5): Commitment recommendation, Interruption rate, Throughput, Unplanned work, Work in progress

### Community 93 - "Intake Demo Generator"
Cohesion: 0.60
Nodes (4): data/demo-intake-bundle.json, add_wd(), build(), main()

### Community 94 - "Demo Bundle Generator"
Cohesion: 0.70
Nodes (4): add_wd(), build(), main(), wdays()

### Community 95 - "Series Merge"
Cohesion: 0.50
Nodes (4): merge_series(), Fields on which a recorded row and a re-derivation differ. Which field moved…, One series, with each row saying which kind of evidence it is. `computed`…, series_disagreements()

### Community 96 - "Import Date Parsing"
Cohesion: 0.50
Nodes (4): Adding an import format, fullYear(), parseDate(), serialToISO()

### Community 97 - "Recipient Validators"
Cohesion: 0.50
Nodes (4): js_problems_for(), `problemsIn` from forge/src/recipients.js, over one config., `recipients.js` and `serve_live.recipient_problems` are one rule, twice. That…, test_the_two_recipient_validators_agree()

### Community 98 - "Two Transports Test"
Cohesion: 0.50
Nodes (4): What `scripts/serve_live.py` really puts on the wire, for both routes. The…, One contract, two transports. The page reaches live mode either over a same-…, _serve_live_bodies(), test_the_two_transports_answer_the_same_shape()

### Community 99 - "Series Checks"
Cohesion: 0.50
Nodes (4): The durable sprint series — ADR 0015, roadmap item 4. Two halves, and the split…, Whether a route refused. Reported by exception type, not by grepping a sentence…, _refuses(), series_checks()

### Community 100 - "Cross-team Roll-up"
Cohesion: 0.67
Nodes (3): v1.50.0 Cross-team rollup started, v1.51.0 Cross-team rollup wired, ADR 0023 A Cross-Team Rollup Spans What the Reader Can See

## Ambiguous Edges - Review These
- `size_stability()` → `size_stability(): the interchangeable-items assumption is checked`  [AMBIGUOUS]
  docs/adr/0006-forecast-in-items-not-points.md · relation: references
- `clean_dataset()` → `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md · relation: references
- `clean_dataset()` → `People picker searches by name, stores the id, projects to an allow-list of fields`  [AMBIGUOUS]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md · relation: semantically_similar_to

## Knowledge Gaps
- **319 isolated node(s):** `SLOT`, `S`, `CARRIES_A_FIGURE`, `input`, `MAIL_CONFIG` (+314 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 685 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `size_stability()` and `size_stability(): the interchangeable-items assumption is checked`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `clean_dataset()` and `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `clean_dataset()` and `People picker searches by name, stores the id, projects to an allow-list of fields`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **Why does `ADR 0008: If we ship on Forge, Forge calls a hosted calculator` connect `Founding ADRs & Badge` to `Sequencing Without Scores`, `Service Suite Checks`, `CLAUDE.md Constraints & ADR Index`, `Hosted Calculator (Retired)`, `Calculator Retirement (ADR 0031)`, `Jira OAuth Login`, `Dashboard Forecast Rendering`, `Live Mode Server`, `Security Suite`, `Facts Pack Metrics`, `Build Script & Pages`, `Forecast Build & Refusals`, `Forecast Log & Claims`, `Intake Tool Entry Points`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `CLAUDE.md working constraints` connect `CLAUDE.md Constraints & ADR Index` to `Organisation Config Rules`, `Hosted Calculator (Retired)`, `Agent Skill & Templates`, `Calculator Retirement (ADR 0031)`, `Refusal Thresholds`, `Business Value & Roll-ups`, `Roadmap & Permission ADRs`, `Issue Normalisation & Escaping`, `Security Suite`, `Refusals & Two Transports`, `Brief Access & Permission ADRs`, `Founding ADRs & Badge`, `Items Not Points Glossary`, `README & Agent Principles`, `Page Constraints & Contributing`, `Architecture & One Implementation`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `Architecture in one paragraph` connect `Architecture & One Implementation` to `Organisation Config Rules`, `WASM Parity & CI Suites`, `Issue Selection & Slicing`, `CLAUDE.md Constraints & ADR Index`, `Bridge Adapter & Jobs`, `Calculator Retirement (ADR 0031)`, `Runtime Asset Packer`, `Facts Pack Metrics`, `Build Script & Pages`, `In-function Python Runtime`, `Forecast Log & Claims`, `Intake Tool Entry Points`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **What connects `SLOT`, `S`, `CARRIES_A_FIGURE` to the rest of the system?**
  _319 weakly-connected nodes found - possible documentation gaps or missing edges._