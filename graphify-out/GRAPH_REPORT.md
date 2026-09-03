# Graph Report - delivery-value-dashboard  (2026-09-03)

## Corpus Check
- 21 files · ~464,371 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2005 nodes · 4165 edges · 108 communities (96 shown, 11 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 349 edges (avg confidence: 0.77)
- Token cost: 364,030 input · 0 output

## Community Hubs (Navigation)
- Weekly Brief Composition
- Service Contract Tests
- Organisation Config & Candidacy
- Forge Async Jobs
- Forge Resolver & Runbook
- Early Forge Changelog & A11y Suite
- Agent Tool Tests
- Page Shell & Org Config Docs
- Forge Context & Audit Shapes
- Import Pipeline
- Jira Issue Normalisation
- Hosted Calculator (Retired)
- Import Wizard Screens
- Dashboard Forecast Rendering
- Root Package & Flow Glossary
- Jira OAuth Login
- Calculator Retirement (ADR 0031)
- Later ADRs (0020-0029)
- Security Suite
- Manifest & Business Value Field
- Routes Projection & Refusals
- Runs on Atlassian Research
- Live Mode Server
- Browser Suites & Early Forge History
- Monte Carlo Forecaster
- Dashboard Render Core
- Roadmap & Brief Delivery History
- Manifest Hostnames & Realms
- Forge Package Dependencies
- Forge Runbooks
- WASM Parity & CI Suites
- Intake Ask 030
- Dashboard Charts & Drilldowns
- Delivery Data Fetcher
- Dashboard Screenshot
- Agent Skill & Templates
- Intake Sizing
- Issue Selection & Slicing
- Durable Series
- Intake Ask 014
- Intake Ask 015
- Runtime Asset Packer
- Brief Access & Permission ADRs
- Jira Client Fields
- Live Jira Backend
- Tile Picker & Presets
- Facts Pack Metrics
- Intake Ask 016
- Bridge Adapter & Forge README
- Refusal ADRs
- Dashboard Org Config Mirror
- CLAUDE.md Constraints & ADR Index
- Durable Series ADRs
- Demo & Burndown Scripts
- Forecast Log & Claims
- Refusal Thresholds
- Contexts & Live Mode Docs
- In-function Python Runtime
- Units & Size Stability
- Forecast Build & Commitment
- Intake Sizing
- Sample Bundle & History Rows
- Context Picker Screenshot
- Early Dashboard Releases
- Foundational ADRs
- Connection Probe
- Manifest Wiring Tests
- Product Intake Concepts
- Context Loading & Rollup
- README & Agent Principles
- WASM Test Harness
- Dashboard Review & No People Metrics
- Data Format & Dashboard Review
- Sequencing & Value Basis Field
- Value Basis & No Priority Score
- Bundle Backend
- Service Computes Nothing Tests
- History Series
- Intake Demo Generator
- Architecture & One Implementation
- Series Merge
- Subtask Counting
- Intake Glossary
- Jira Token Transport
- CI Workflow & Parity Suite
- Candidate Asks Mirror
- Bundle Sequencing
- Window Forecast Tests
- Items Not Points Glossary
- Calibration Notes
- Team Load Glossary
- Window & Preset Helpers
- Forecast Claims
- Recipient Validator Parity
- Two Transports Parity Test
- Series Refusal Checks
- Queue Cost Scenarios
- Refresh Script
- Stored Id Display Test
- Manifest Matches Code Test
- Ageing
- Risk Register
- Scope Growth
- Value Basis
- Intake Reproducibility
- Intake Blind Spots
- Pinned Residency

## God Nodes (most connected - your core abstractions)
1. `ADR 0031 — The forecast runs inside the Forge function, and the calculator is retired` - 56 edges
2. `Forge app manifest` - 49 edges
3. `check()` - 48 edges
4. `CLAUDE.md working constraints` - 47 edges
5. `render()` - 42 edges
6. `Hosting the calculator (retired 2026-09-03)` - 38 edges
7. `Finishing the Forge route — runbooks` - 36 edges
8. `check()` - 28 edges
9. `The commercial roadmap` - 28 edges
10. `build()` - 27 edges

## Surprising Connections (you probably didn't know these)
- `People picker searches by name, stores the id, projects to an allow-list of fields` --semantically_similar_to--> `clean_dataset()`  [AMBIGUOUS] [semantically similar]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md → service/routes.py
- `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)` --references--> `clean_dataset()`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md → service/routes.py
- `Commitment recommendation` --references--> `recommend_commitment()`  [INFERRED]
  CONTEXT.md → agent/tools/forecast.py
- `1.29.0 — The scheduled brief reads the board and sends it` --references--> `editabilityFor()`  [EXTRACTED]
  CHANGELOG.md → forge/src/index.js
- `What counts as a finished epic` --references--> `epic_sizes()`  [EXTRACTED]
  docs/product-intake.md → agent/tools/intake.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Retiring the hosted calculator, route by route (ADR 0031)** — changelog_1_75_0, changelog_1_76_0, changelog_1_76_1, changelog_1_76_2, changelog_1_77_0, changelog_1_77_1, changelog_1_77_2, changelog_1_77_3, changelog_1_77_4, changelog_1_77_5, changelog_1_78_0, changelog_1_78_1, docs_adr_0031_the_forecast_runs_inside_the_forge_function, forge_manifest_no_egress, service_routes, forge_src_runtime [EXTRACTED 1.00]
- **The async job path: resolver pushes, consumer computes, adapter polls** — forge_manifest_function_simulation_fn, forge_manifest_consumer_simulation_consumer, forge_src_jobs, docs_adr_0031_the_forecast_runs_inside_the_forge_function_job_row, docs_adr_0031_the_forecast_runs_inside_the_forge_function_retry_guard, forge_bridge_bridge, docs_adr_0031_the_forecast_runs_inside_the_forge_function_payload_chunks_in_app_storage [INFERRED 0.85]
- **One implementation of every figure, held by byte-for-byte parity** — claude_agent_never_does_arithmetic, claude_nothing_between_tools_and_reader_does_arithmetic, docs_adr_0031_the_forecast_runs_inside_the_forge_function_one_implementation_of_every_figure, service_readme_routes_compute_nothing, tests_test_wasm, tests_test_service [INFERRED 0.85]
- **Refusal family: below the evidence, say the evidence is absent rather than print a plausible figure** — docs_adr_0007_refuse_rather_than_widen_refuse_rather_than_widen, docs_adr_0007_refuse_rather_than_widen_evidence_absent_not_noisy, docs_adr_0010_an_empty_selection_is_a_refusal_empty_selection_refusal, docs_adr_0011_a_kanban_context_is_a_window_not_a_clock_window_not_a_clock, docs_adr_0013_the_brief_is_written_inside_the_tenant_refusals_not_passed_through_model, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_refusal_not_a_claim [EXTRACTED 1.00]
- **Allow-list projection: stores and payloads hold named fields only, never issue text or contact details** — docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_scope_allow_list, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_people_picker_allow_list, docs_adr_0015_a_durable_series_stores_what_jira_forgets_counts_never_issue_text, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_claim_fields_allow_list, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_app_store_inventory, docs_adr_0021_the_audit_log_is_operational_and_says_so_audit_entry_allow_list [INFERRED 0.85]
- **Roadmap item 5: permission mirroring, its three exposures and their accepted answers** — docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_permission_mirroring_by_asuser, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_three_exposures, docs_adr_0019_a_recorded_row_is_a_fact_about_the_board_row_belongs_to_board, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_anchor_issue_access_control, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_restrict_browse, docs_adr_0013_the_brief_is_written_inside_the_tenant_asapp_reversal, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_offline_user_impersonation_deferred [EXTRACTED 1.00]
- **Decisions driven by the credible-wrong-number failure class** — docs_adr_0023_a_cross_team_rollup_spans_what_the_reader_can_see_rollup_does_not_forecast, docs_adr_0024_a_parent_and_its_subtasks_are_one_piece_of_work_count_subtasks, docs_adr_0026_items_and_value_are_counted_from_two_different_sets_two_sets_items_and_value, docs_forecasting_agent_reporting_scope_is_not_forecasting_scope [INFERRED 0.85]
- **Pyodide-in-function route: research, probes, manifest functions** — docs_research_2026_09_01_runs_on_atlassian_badge_pyodide_in_forge_function, docs_research_2026_09_02_second_probe_consumer_and_snapshot_wasm_probe_2, docs_research_2026_09_01_forge_async_events_consumer_module [INFERRED 0.95]
- **Connection check: bridge, read board, projection** — forge_probe_index_bridge_check, forge_probe_index_read_board, forge_probe_index_projection_check, forge_manifest_connection_check_adminpage [EXTRACTED 1.00]
- **Source > Project > Board > Sprint selection cascade** — docs_screenshots_context_picker_source_badge, docs_screenshots_context_picker_project_selector, docs_screenshots_context_picker_board_selector, docs_screenshots_context_picker_sprint_selector [INFERRED 0.85]
- **Dashboard header strip** — docs_screenshots_context_picker_header_line, docs_screenshots_context_picker_sprint_goal, docs_screenshots_context_picker_data_bundle_pill, docs_screenshots_context_picker_sprint_health_pill, docs_screenshots_context_picker_toolbar_actions [EXTRACTED 1.00]
- **Narrative panel, KPI tiles and risk list are three views of the same sprint facts** — docs_screenshots_dashboard_what_this_sprint_means, docs_screenshots_dashboard_kpi_tiles, docs_screenshots_dashboard_risks_and_what_to_do [INFERRED 0.85]
- **Flow charts: burndown, cycle time with waiting, work item age** — docs_screenshots_dashboard_burndown_with_scope_changes, docs_screenshots_dashboard_cycle_time_waiting_chart, docs_screenshots_dashboard_work_item_age [INFERRED 0.75]
- **CSV import wizard: upload, check column mapping, load** — docs_screenshots_import_mapping_upload_a_file_tab, docs_screenshots_import_mapping_step_2_of_3_check_column_mapping, docs_screenshots_import_mapping_column_mapping_table, docs_screenshots_import_mapping_jira_export_csv [EXTRACTED 1.00]
- **Created, started and resolved dates drive lead time, cycle time and burndown** — docs_screenshots_import_mapping_created_date_field, docs_screenshots_import_mapping_started_date_field, docs_screenshots_import_mapping_resolved_date_field, docs_screenshots_import_mapping_lead_time_metric, docs_screenshots_import_mapping_cycle_time_metric, docs_screenshots_import_mapping_burndown_metric [EXTRACTED 1.00]
- **Import wizard step 3: review counts, warnings and preview rows before applying** — docs_screenshots_import_preview_step_3_check_before_applying, docs_screenshots_import_preview_summary_tiles, docs_screenshots_import_preview_no_business_value_warning, docs_screenshots_import_preview_preview_table, docs_screenshots_import_preview_apply_to_the_dashboard [EXTRACTED 1.00]
- **Three ways in: upload a file, connect Jira/Asana, read the data format** — docs_screenshots_import_mapping_upload_a_file_tab, docs_screenshots_import_mapping_connect_jira_asana_tab, docs_screenshots_import_mapping_data_format_tab [EXTRACTED 1.00]

## Communities (108 total, 11 thin omitted)

### Community 0 - "Weekly Brief Composition"
Cohesion: 0.06
Nodes (63): ADR-0005, ADR-0007, ADR-0013, ADR-0014, briefMessages(), composeBrief(), contentText(), DECLINED (+55 more)

### Community 1 - "Service Contract Tests"
Cohesion: 0.05
Nodes (61): 1.77.0 — Sequencing runs inside the Forge function as a job, and the page cannot tell, 1.77.1 — The facts route is answered inside the Forge function, ask_assembly_checks(), audit_log_checks(), body_keys_reach_a_reader(), business_value_checks(), check(), counting_checks() (+53 more)

### Community 2 - "Organisation Config & Candidacy"
Cohesion: 0.06
Nodes (49): meta.calendar must equal inputs.calendar, burndown(), Reconstruct a daily burndown from resolution dates and mid-sprint adds. **Moved…, add_working_days(), candidate_answer(), candidate_issues(), counted_note(), from_dataset() (+41 more)

### Community 3 - "Forge Async Jobs"
Cohesion: 0.06
Nodes (48): ADR-0017, ADR-0018, The job row, consumer simulation-consumer (queue simulations), chunkPayload(), collect(), CONSUMER_ROUTES, FAILED_SENTENCE (+40 more)

### Community 4 - "Forge Resolver & Runbook"
Cohesion: 0.08
Nodes (39): ADR-0008, ADR-0009, The weekly brief — deployed, and it refuses, function weekly-brief-fn (index.weeklyBrief, 120 s, 1024 MB), appFieldsFor(), ASK_TEXT_FIELDS, assertNoFreeText(), audit() (+31 more)

### Community 5 - "Early Forge Changelog & A11y Suite"
Cohesion: 0.08
Nodes (45): 1.0.0 — First version, 1.12.0 — Ask sequencing is on the tile, 1.12.1 — WCAG reflow failure from the third forecast mode, 1.12.2 — The 320px reflow failure was a sparkline, 1.12.3 — The demo shows the Monte Carlo tile, 1.12.4 — The theme button lied on a dark-preferring machine, 1.12.5 — Two grid rows did not add up to 12, 1.13.0 — The tiles can be put in your own order (+37 more)

### Community 6 - "Agent Tool Tests"
Cohesion: 0.07
Nodes (47): check(), _intake_ds(), near(), An unauthenticated pull must stop, not degrade — found against live Jira.…, The facts pack reports the sprint; the forecaster uses all history. Conflating…, `/rest/api/3/search` was removed; `/search/jql` pages by token. Not a URL swap.…, The three ways a forecast can be built from the wrong slice of the file. All…, The headline output: is the range driven by not knowing the size, or by normal… (+39 more)

### Community 7 - "Page Shell & Org Config Docs"
Cohesion: 0.05
Nodes (45): GitHub Pages publish job, build(), build_split(), main(), The same sources as separate files, for a host that forbids inline assets. The…, The iframe forbids inline style and script, so the Forge build is split, Added-mid-sprint inferred from created date, All-numeric date disambiguation (+37 more)

### Community 8 - "Forge Context & Audit Shapes"
Cohesion: 0.06
Nodes (44): 1.69.1 — The value tile stops guessing, 1.70.0 — A key a producer emits and no consumer takes is a failing test, 1.71.0 — An excluded epic is counted, and a refusal that disproved itself, ADR-0021, No text from the page reaches Jira, appendAudit(), AUDIT_EVENTS, AUDIT_FIELDS (+36 more)

### Community 9 - "Import Pipeline"
Cohesion: 0.07
Nodes (39): Import problem issue template, 1.7.0 — Overtime removed; accessibility and security suites, Escape at output, once, UI colour tokens are separate from the chart palette, Built file makes zero network calls and uses zero browser storage, Adding an import format, Charts follow the colour rules, Derived data is recomputed, never inherited (+31 more)

### Community 10 - "Jira Issue Normalisation"
Cohesion: 0.06
Nodes (43): 1.16.5 — The two transports agree what a window is, 1.16.6 — A board with no sprints is offered windows, ADR-0011, ADR-0024, ADR-0025, ADR-0026, ADR-0027, ADR-0028 (+35 more)

### Community 11 - "Hosted Calculator (Retired)"
Cohesion: 0.06
Nodes (43): 1.19.0 — The hosted calculator has a plan; two of three blockers were code, 1.20.0 — Provisioning wizard and deploy workflow, 1.20.1 — Deployed and reported dead: /healthz swallowed by Google's front end, 1.20.2 — The calculator is hosted; a trailing-newline secret bug, 1.20.3 — The cold start is measured, 1.21.0 — The calculator is tenant-aware in production, 1.38.1 — The fetcher is importable without a tracker dependency, 1.39.0 — The calculator image takes Debian's security updates at build time (+35 more)

### Community 12 - "Import Wizard Screens"
Cohesion: 0.06
Nodes (42): Import mapping screenshot, Assignee field, Auto-detected mapping (green check status), Burndown and completion, Column mapping table (Dashboard field / Your column / Example value / Status), Connect Jira / Asana tab, Created date field (drives ageing and lead time), Custom field mapping (story points, started date) (+34 more)

### Community 13 - "Dashboard Forecast Rendering"
Cohesion: 0.10
Nodes (30): 1.16.10 — Cycle time works inside a Jira tenant via statusTransitions, 1.16.11 — A flow board hides the three tiles that never can measure it, 1.16.12 — A flow health score for a board with no sprints, 1.16.9 — The risk register names the rules it did not run, ADR-0004, ADR-0023, auditHtml(), bindForecastInputs() (+22 more)

### Community 14 - "Root Package & Flow Glossary"
Cohesion: 0.06
Nodes (35): Board, Bundle, Cumulative flow, Cycle time, Flow board, Flow health, Health score, Lead time (+27 more)

### Community 15 - "Jira OAuth Login"
Cohesion: 0.10
Nodes (24): Connecting Jira and Asana, Fetcher with an API token (scripts/fetch_delivery_data.py), MCP connectors and CSV export routes, OAuth 2.0 (3LO) route via scripts/jira_auth.py, OAuth 2.0 (3LO) for a Jira that is not your own, accessible_resources(), authorize_url(), _Catcher (+16 more)

### Community 16 - "Calculator Retirement (ADR 0031)"
Cohesion: 0.08
Nodes (34): 1.77.2 — The forecast is answered inside the Forge function, 1.77.3 — The forecast is a job, 1.77.4 — The trend series is answered inside the Forge function, 1.77.5 — The burndown is answered inside the Forge function, 1.78.0 — The remote is gone; every figure computed inside the Forge function, 1.78.1 — The hosted service's own files go, Calculator, ADR 0031 — The forecast runs inside the Forge function, and the calculator is retired (+26 more)

### Community 17 - "Later ADRs (0020-0029)"
Cohesion: 0.09
Nodes (31): ADR 0020: The anchor issue is the brief's access control, and impersonation is deferred, Administer Jira global permission refused, Offline user impersonation (asUser(accountId), allowImpersonation) is deferred, not rejected, Conditions that would revive impersonation, ADR 0021: The audit log is operational, and says so, problemsInAuditEntry: counts, flags, field names, one actor identity, An app writing its own rewritable log is not tamper-evident, Build the operational log; say plainly it is not a compliance record (+23 more)

### Community 18 - "Security Suite"
Cohesion: 0.14
Nodes (28): ADR 0001: The dashboard is one self-contained HTML file, Threat model: the file gets emailed, Single self-contained HTML file, Forge CSP forbids inline style/script; split build and CSSOM setter wrap, ADR 0022: SSO is inherited, because this app owns no identity, No Atlassian credential, session or auth module in the app, The personal API token path lives only in scripts/, SSO is inherited because the app owns no identity (+20 more)

### Community 19 - "Manifest & Business Value Field"
Cohesion: 0.09
Nodes (27): One issue's business value as it should be counted, or zero. The one place the…, value_of(), 1.54.0 — The app declares a Business Value field, 1.54.1 — The Business Value field was declared, read, and never requested, 1.55.0 — Business value on an epic reached nothing; epics fetched separately, The manifest declares no remote and must not gain one, Every Forge scope is read-only except two named ones, Business value counted at one hierarchy level (+19 more)

### Community 20 - "Routes Projection & Refusals"
Cohesion: 0.15
Nodes (25): 1.66.0 — The Forge sequencing refusal is gone, assertAsksCarryNoText / _refuse_ask_text, Exception, assertAsksCarryNoText(), check_sequence(), clean_dataset(), _clean_issue(), _iso_or_none() (+17 more)

### Community 21 - "Runs on Atlassian Research"
Cohesion: 0.09
Nodes (27): Epic grouping field chosen once for the whole set, What counts as a finished epic, The sizing ladder (tshirt / reference-class / explicit), T-shirt sizes calibrated per board, Async event at-least-once delivery and retries, Consumer function limits: 900 s, 1,024 MB, Forge consumer module, Forge Realtime as an alternative to polling (+19 more)

### Community 22 - "Live Mode Server"
Cohesion: 0.12
Nodes (22): append_audit(), Handler, A mirror of `problemsIn` in forge/src/recipients.js, in Python. A second…, One board's recorded rows. Missing and unreadable both read as empty. Keyed by…, One board's forecast log. Missing and unreadable both read as empty — a caller…, Mirrors `appendAudit` in forge/src/audit.js, bound included. Best-effort and…, Whether this observation may be written. Mirrors `recordable` in…, The trend series for the board `cid` belongs to, and the recording of it. The… (+14 more)

### Community 23 - "Browser Suites & Early Forge History"
Cohesion: 0.13
Nodes (25): 1.16.1 — The dashboard scored an empty sprint 66/100, 1.16.2 — Reconciled with the per-site calendar; a missing calendar scored as bad delivery, 1.40.0 — Three things a two-sprint board made visible, 1.40.1 — The same false basis in the next clause, 1.40.2 — The roadmap defines item 4's letters; 4b corrected to 4a, An empty selection is a refusal, not a zero, Say what you cannot know, check() (+17 more)

### Community 24 - "Monte Carlo Forecaster"
Cohesion: 0.16
Nodes (24): add_working_days(), CountForecast, cycle_times(), _d(), DateForecast, forecast_completion(), forecast_count_by_date(), full_history_days() (+16 more)

### Community 25 - "Dashboard Render Core"
Cohesion: 0.12
Nodes (25): 1.16.7 — The page knows a window is not a clock, 1.16.8 — Sprint-shaped tiles refuse on a flow board, Drill-down, Adding a metric, commitU(), derive(), fetchSeries(), filtered() (+17 more)

### Community 26 - "Roadmap & Brief Delivery History"
Cohesion: 0.09
Nodes (25): 1.30.0 — Item 3 runs end to end against a real tenant; only a site setting remains, 1.31.0 — The recipient picker takes a name, not an account id, 1.32.0 — A brief was delivered; roadmap item 3 is done, 1.33.0 — The recipient field shows who those ids are, 1.34.0 — The account-ID field is folded away; the named list is edited, 1.35.0 — The read-only recipients view shows names, 1.36.0 — A closed sprint got better the longer ago it was, 1.47.0 — The anchor issue is the brief's access control (+17 more)

### Community 27 - "Manifest Hostnames & Realms"
Cohesion: 0.11
Nodes (24): 1.72.4 — The roadmap named engineering already built; glossary redefines ask and candidate, 1.73.0 — Hostnames and realms decided before the first install, 1.74.0 — A third Cloud Run region, London, and a realm guard, 1.74.1 — GB is declared; a UK tenant's numbers are computed in London, 1.74.2 — The realm guard did not run on the change it exists for, 1.74.3 — ADR 0008 amended: a WebAssembly route exists and is measured, 1.74.4 — The manifest's badge comment corrected, 1.75.0 — The app will run its forecast inside the Forge function; the calculator will be retired (+16 more)

### Community 28 - "Forge Package Dependencies"
Cohesion: 0.08
Nodes (23): esbuild, @forge/api, @forge/bridge, @forge/events, @forge/kvs, @forge/llm, dependencies, @forge/api (+15 more)

### Community 29 - "Forge Runbooks"
Cohesion: 0.10
Nodes (23): 1.29.1 — The scheduled trigger runs the new code; iframe clipping reported, 1.29.2 — layout: blank was wrong too, 1.29.3 — The frame's document measured; overflow confirmed, cause said to be the host, 1.29.4 — emitReadyEvent changed nothing; synthetic input suspect, 1.29.5 — There was no bug: the dashboard scrolls on Forge with a mouse, 1.64.0 — The Forge build had lost its inline style attributes to CSP, 1.65.0 — A declared candidate becomes an ask, 1.72.2 — A future sprint was told its dataset was too old (+15 more)

### Community 30 - "WASM Parity & CI Suites"
Cohesion: 0.15
Nodes (22): The suites CI enforces, _intake_bodies(), project(), The measurement the architecture is built on, asserted rather than recalled.…, The service's answer is the tool's answer, to the byte., The demo intake bundle, projected, and its asks stripped of every word. What…, A different calendar is a different answer — including, sometimes, no answer., One team's slice, projected — exactly what the Forge resolver sends. (+14 more)

### Community 31 - "Intake Ask 030"
Cohesion: 0.09
Nodes (22): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+14 more)

### Community 32 - "Dashboard Charts & Drilldowns"
Cohesion: 0.19
Nodes (23): cycleRows(), drawTable(), littlesLaw(), pctile(), renderAge(), renderBurn(), renderCfd(), renderCycle() (+15 more)

### Community 33 - "Delivery Data Fetcher"
Cohesion: 0.16
Nodes (21): Started date lives in the changelog, not the export, asana_pull(), build_burndown(), configure(), connect_jira(), d(), jira_bundle(), jira_pull() (+13 more)

### Community 34 - "Dashboard Screenshot"
Cohesion: 0.11
Nodes (22): Dashboard screenshot (Sprint 24 — delivery and value), Burndown with scope changes shown, Business value delivered ($34,800 estimated, with stated basis), Can we trust the forecast? (committed vs completed, last six sprints), How long work takes and how much is waiting (flow efficiency per closed item), Every figure traces back to an issue (footer principle, click-through links), Filter row (Source, Project, Board, Sprint, Person, Epic, Type, Status, Find), Flow efficiency (32% of elapsed time was active work) (+14 more)

### Community 35 - "Agent Skill & Templates"
Cohesion: 0.13
Nodes (21): Sprint 24 delivery brief (worked example), Sprint 24 team report (worked example), delivery-report agent skill, Evidence tagging, Prohibited outputs, Agent refusal thresholds, Agent sequence: load, diff, forecast, reconcile, write, log, score, Exec brief template (+13 more)

### Community 36 - "Intake Sizing"
Cohesion: 0.18
Nodes (20): attribute_uncertainty(), board_issues(), capacity(), _d(), epic_sizes(), _fmt(), _fmt_sequence(), forecast_ask() (+12 more)

### Community 37 - "Issue Selection & Slicing"
Cohesion: 0.17
Nodes (20): cross_team_boards(), cross_team_label(), cross_team_members(), forecast_for(), Which issues a forecast reads, and what it is told about them. This is the…, The context a forecast is *for*, and the sprints a rollup stands for. Returns…, Which contexts a forecast for `cid` would sample, and how it chose them.…, Run the real forecaster for one context. Returns None for an unknown id. The… (+12 more)

### Community 38 - "Durable Series"
Cohesion: 0.12
Nodes (20): 1.37.0 — The durable series has a module and a shape, and neither stores an issue, 1.43.0 — The trend window is a setting; item 4 done, 1.44.0 — Item 5 started by surveying two exposures item 4 created, 1.45.0 — A recorded sprint row belongs to the board, ADR-0015, Item 4: Durable sprint history — done 2026-08-29, COMPARED, entryFrom() (+12 more)

### Community 39 - "Intake Ask 014"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 40 - "Intake Ask 015"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 41 - "Runtime Asset Packer"
Cohesion: 0.11
Nodes (18): 1.76.0 — The calculator's answers are one module, and the socket is another, 1.76.1 — The Python runtime travels into the Forge function as a generated module, Generated at deploy, never committed, { BOOT, writeSources }, digest, files, hash, HERE (+10 more)

### Community 42 - "Brief Access & Permission ADRs"
Cohesion: 0.18
Nodes (19): ADR 0013: The brief is written inside the tenant; only the file leaves, Superseded in part: the scheduled read takes asApp() deliberately, The file leaves: mailing is the one boundary crossing (later closed by ADR 0014), The brief is written by Forge LLMs in Atlassian's runtime, A scheduled trigger runs with no user principal, ADR 0014: Jira sends the brief, and the read-only rule bends by allow-list, forge/src/compose.js keeps the send provable without deploying, Jira sends the brief via issue notify; nothing leaves (+11 more)

### Community 43 - "Jira Client Fields"
Cohesion: 0.15
Nodes (9): Jira, The Jira surface this script needs, over either transport. `url` is the…, Who this connection is authenticated as — `(identity, None)`, or `(None, why)`…, Locate the story-point and sprint custom fields by display name., The field that says an issue is an ask — ours, or the site's own. `"app"` is…, The field carrying an ask's t-shirt band — ours, or the site's own. Same rule…, This app's own Business Value and Value Basis fields on this site. **Matched on…, The board's epics as issues — ADR 0026. **Epics are not on a scrum board.**… (+1 more)

### Community 44 - "Live Jira Backend"
Cohesion: 0.13
Nodes (12): JiraBackend, main(), The third part of a flow board's context id. Prefixed rather than bare, so a…, Which issues are *in* a window, as a JQL predicate. The membership ADR 0011…, One selectable window, in the shape the sprint entry above uses. Field for…, Queries Jira on demand. Sprint lists are cheap; issues are fetched only when a…, The saved filter behind a board, which is how plain JQL is scoped to one. The…, Sequencing sizes asks against the board's completed epics and its interruption… (+4 more)

### Community 45 - "Tile Picker & Presets"
Cohesion: 0.18
Nodes (19): announcePicker(), applyOrder(), applyTiles(), buildPicker(), buildPickerList(), download(), focusMover(), moveTile() (+11 more)

### Community 46 - "Facts Pack Metrics"
Cohesion: 0.19
Nodes (17): _d(), diff(), elapsed_days(), facts(), _get(), in_sprint(), is_done(), main() (+9 more)

### Community 47 - "Intake Ask 016"
Cohesion: 0.11
Nodes (17): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+9 more)

### Community 48 - "Bridge Adapter & Forge README"
Cohesion: 0.12
Nodes (15): ADR-0031, Sequencing is asynchronous, The bridge, and why the page does not know it is on Forge, Item 1: OAuth app on the Marketplace — done, as both routes, ceilingBody(), collectJob(), JOB_ROUTES, POLL_INTERVALS_MS (+7 more)

### Community 49 - "Refusal ADRs"
Cohesion: 0.18
Nodes (17): ADR 0007: Below the evidence thresholds, refuse rather than widen the interval, Refusal clause: the evidence is absent, not noisy, Refuse rather than widen the interval, ADR 0010: An empty selection is a refusal, not a zero, A composite drops an unmeasurable component and names it, An empty selection is a refusal, not a zero, Below half the weight the composite refuses, A single 'no data' banner and dimming were rejected (+9 more)

### Community 50 - "Dashboard Org Config Mirror"
Cohesion: 0.18
Nodes (17): applyWorkflow(), boardStatuses(), buildView(), contextWorkingDays(), inferredSentence(), inferredStatuses(), normalise(), normaliseIssue() (+9 more)

### Community 51 - "CLAUDE.md Constraints & ADR Index"
Cohesion: 0.14
Nodes (16): CLAUDE.md working constraints, Credentials live only in the fetcher's environment, dist/ is committed on purpose, Monte Carlo is seeded and reproducible, Live mode has two transports and one set of body shapes, When you change something, Zero-throughput days stay in the sample, Live mode (+8 more)

### Community 52 - "Durable Series ADRs"
Cohesion: 0.18
Nodes (16): Durable series, Reconstructed row, Recorded row, The disclosure must name the right cause, ADR 0015: A durable series stores what Jira forgets, and re-derivation is a labelled fallback, The store holds counts, never issue text, A sprint's row is written once when it closes and read thereafter, Re-derivation is a labelled fallback, and disagreements are said aloud (+8 more)

### Community 53 - "Demo & Burndown Scripts"
Cohesion: 0.20
Nodes (14): Repository layout, _d(), in_sprint(), main(), Same rule as the facts pack: in scope unless finished before the start., rebuild(), working_days(), build_cards() (+6 more)

### Community 54 - "Forecast Log & Claims"
Cohesion: 0.17
Nodes (15): problems_in_claim(), What is wrong with one logged claim, as sentences. Empty means storable.…, Score every claim whose horizon has passed, from completions in its window.…, Score past forecasts against what actually happened. Without this the agent is…, The log, bounded, oldest resolved entries first. Reports what it dropped. No…, One board's forecast log, brought up to date, and what it now scores.…, resolve_claims(), score_calibration() (+7 more)

### Community 55 - "Refusal Thresholds"
Cohesion: 0.14
Nodes (15): Refusal thresholds are hard, not advisory, Agent executive summary, Published calibration score that stops probabilities, Executive brief and team report from one set of facts, Rollout: shadow, team report, exec brief, automate, Forecasting agent design outline, Backtest with non-overlapping windows and full horizons, Brier score over the forecast log (+7 more)

### Community 56 - "Contexts & Live Mode Docs"
Cohesion: 0.13
Nodes (15): ADR 0002: The page never queries Jira or Asana; data arrives as a bundle, Contexts fetched up front into a bundle, Live mode: local server on 127.0.0.1, ADR 0023 Cross-team roll-up spans what the reader can see, Cross-team roll-up, Cross-team roll-up refuses to forecast, What an ask is inside Jira (open product question), The page cannot call Jira or Asana itself (+7 more)

### Community 57 - "In-function Python Runtime"
Cohesion: 0.21
Nodes (13): How the runtime travels, answer(), baseDir(), fs, load(), loadAssets(), os, path (+5 more)

### Community 58 - "Units & Size Stability"
Cohesion: 0.16
Nodes (14): agent/SKILL.md, Is item-count forecasting still safe for this team? Counting items assumes…, size_stability(), 1.2.0 — Reporting & forecasting agent, 1.3.0 — Item counts made the unit end to end, The agent never does arithmetic, Size stability, ADR 0006: Forecasts count items, never story points (+6 more)

### Community 59 - "Forecast Build & Commitment"
Cohesion: 0.20
Nodes (13): build(), main(), Historical mid-sprint scope growth, as a multiplier per period. Needs the…, How many items can this team commit to in a sprint, and at what confidence?…, Returned instead of a forecast when the data cannot support one. The agent must…, window_days=None means every day of imported history, which is the default here…, recommend_commitment(), Refusal (+5 more)

### Community 60 - "Intake Sizing"
Cohesion: 0.19
Nodes (13): Derive S/M/L/XL bands from the team's own completed epics. Quartiles, not a…, Turn a product ask into a distribution of item counts., Refusal, size_ask(), Sizing, _triangular(), tshirt_scale(), 1.68.0 — An epic can carry a t-shirt size (+5 more)

### Community 61 - "Sample Bundle & History Rows"
Cohesion: 0.22
Nodes (12): history_row(), One sprint's row of the trend series, as it stood at `as_of`. **Every count…, First answer, corrected: wipItems re-derives correctly, History rows are derived from dates at asOfDate, never current status, build_history(), How many sprints of trend the dataset keeps. One reader, so the fetcher and…, Append this sprint to whatever history the previous file held, so the trend…, trend_window() (+4 more)

### Community 62 - "Context Picker Screenshot"
Cohesion: 0.22
Nodes (13): Context picker screenshot, Board selector, Context bar (Source / Project / Board / Sprint), Data-as-at timestamp, Data bundle pill (Demo bundle - 3 boards x 6 sprints), Header line (Project · Team · Sprint dates · data as at), Project selector, Source badge (JIRA) (+5 more)

### Community 63 - "Early Dashboard Releases"
Cohesion: 0.23
Nodes (10): 1.4.0 — Items by default with a Points toggle, 1.5.0 — Project, board and sprint filtering; schema 2.0; live mode, 1.5.1 — Performance measured rather than assumed, 1.6.0 — A shareable demo and an executive summary, add_wd(), build(), main(), wdays() (+2 more)

### Community 64 - "Foundational ADRs"
Cohesion: 0.23
Nodes (12): ADR 0005: The tools compute; the agent only narrates, Tools compute; the agent narrates, ADR 0008: If we ship on Forge, Forge calls a hosted calculator, Hosted calculator imports the Python tools unchanged, Pyodide (CPython under WebAssembly) inside the Forge function, Pyodide in the Custom UI iframe (rejected), Runs on Atlassian badge, ADR 0009: One contract, two transports (+4 more)

### Community 65 - "Connection Probe"
Cohesion: 0.32
Nodes (11): Section 1: Bridge, Connection check page (probe), Section 3: What would leave the tenant, Section 2: Reading a board by id, call(), loadBoard(), main(), note() (+3 more)

### Community 66 - "Manifest Wiring Tests"
Cohesion: 0.18
Nodes (12): _code_only(), _manifest_item(), The scalar fields of the manifest list item introduced by `- key: <key>`. Regex…, A scheduled trigger is not a resolver call, and the manifest said it was.…, A route is answered in-function or by the calculator, never both. The migration…, esbuild bundles an undefined identifier without a word. `answerHere` was lost…, JavaScript with its comments stripped, so a check about what the code does is…, Sequencing and the forecast run as async events, and the page cannot tell. ADR… (+4 more)

### Community 67 - "Product Intake Concepts"
Cohesion: 0.22
Nodes (11): Intake mode, Intake brief template, readiness(), Capacity scenario, Cost of the queue, Queue ahead, Readiness, Sequence (+3 more)

### Community 68 - "Context Loading & Rollup"
Cohesion: 0.25
Nodes (11): 1.51.0 — The cross-team roll-up is wired, contextById(), loadContext(), loadRollupMembers(), orgConfigOf(), probeLive(), refreshLive(), renderContextBar() (+3 more)

### Community 69 - "README & Agent Principles"
Cohesion: 0.18
Nodes (10): Deploying: email, shared drive, Pages, board pack, Fetcher script for regular refreshes, The four questions activity reporting fails to answer, MCP connectors once the format has proved itself, Monte Carlo forecasting in the page, Forecasting an ask before any of it exists, Putting the tiles in your own order, Executive and Team tile presets (+2 more)

### Community 70 - "WASM Test Harness"
Cohesion: 0.18
Nodes (10): assets, cases, [casesPath, outPath, modeFlag], HERE, loadMs, require, results, runtime (+2 more)

### Community 71 - "Dashboard Review & No People Metrics"
Cohesion: 0.22
Nodes (10): ADR 0003: The dashboard does not measure people, No hours, overtime, timesheet field; no ranking of individuals, Team load: WIP and unplanned work from issue status, Sprint 24 dashboard review, Health score with the method exposed on hover, One completion figure from a single field, Predictability card with recommended next commitment, Team load card replacing output-per-person and overtime (+2 more)

### Community 72 - "Data Format & Dashboard Review"
Cohesion: 0.20
Nodes (10): Context: one project + board + sprint, Burndown with a scope line and mid-sprint callout, Data format, Burndown carries both units, always, orgConfig.inferredStatuses, started, recovered from the changelog, Units: items by default; calendar days reported, working days simulated, Window context ids on flow boards (win:14d/30d/90d) (+2 more)

### Community 73 - "Sequencing & Value Basis Field"
Cohesion: 0.25
Nodes (9): asks_from_issues(), `(asks, notes)` — every declared candidate on this board, as asks. An ask has…, The refusal sentence for more asks than one sequencing compares, or None. A…, For a set of asks against one team, what each ordering costs the others.…, sequence(), too_many_asks(), 1.57.0 — The app declares a Value Basis field, free text on purpose, Item 7: Cross-team roll-up and intake sequencing — done (+1 more)

### Community 74 - "Value Basis & No Priority Score"
Cohesion: 0.28
Nodes (9): ADR 0004: Intake returns delivery consequence, never a priority score, Delivery consequence of an ordering, No WSJF or value-over-effort priority score, ADR 0027 A value basis is prose carried to a reader, NEVER_SEND / FREE_TEXT_FIELDS boundary, Value Basis custom field (free text), A value basis is prose, never an input, Value figure as a floor with a basis line per item (+1 more)

### Community 75 - "Bundle Backend"
Cohesion: 0.22
Nodes (4): BundleBackend, no_days_yet_note(), Why a sprint's chart has no day on it that has happened yet, or `None`. Mirrors…, Reads an existing bundle file. Used for demos, tests, and for working offline…

### Community 76 - "Service Computes Nothing Tests"
Cohesion: 0.22
Nodes (9): call(), Intake's reference class, over the payload the calculator really receives.…, `service/` is `routes.py` and nothing else. ADR 0031. The hosted calculator's…, One route, answered: `(status, payload)`. The signature kept the shape of the…, A traceback carries field values, and those are the customer's., test_epic_sizing_survives_the_projection(), test_no_internals_leak(), test_refusals() (+1 more)

### Community 77 - "History Series"
Cohesion: 0.29
Nodes (8): history_series(), One row per sprint context, in the order the board runs them. The loop lives…, A context sees the series up to and including itself, never the future. The…, What the page says about sprints that produced no row at all. Separate from…, series_upto(), skipped_note(), 1.39.1 — The trend was empty in the tenant: a sort order, 1.39.2 — A sprint the series could not date left it silently

### Community 78 - "Intake Demo Generator"
Cohesion: 0.32
Nodes (7): 1.8.0 — Product intake, Never compute a priority score, data/demo-intake-bundle.json, Sequence asks mode, add_wd(), build(), main()

### Community 79 - "Architecture & One Implementation"
Cohesion: 0.25
Nodes (8): Architecture in one paragraph, Nothing between the tools and a reader may do arithmetic, One implementation of every figure, service/ README, Anything added must import under Pyodide, routes.py computes nothing, answer(), One route's envelope: `(status, payload)`, no socket and no auth. This is the…

### Community 80 - "Series Merge"
Cohesion: 0.33
Nodes (7): merge_series(), Fields on which a recorded row and a re-derivation differ. Which field moved…, One series, with each row saying which kind of evidence it is. `computed`…, What the page says above the chart. Silent when there is nothing to say. Every…, series_disagreements(), series_note(), 1.38.0 — A Forge tenant has a trend at last (item 4a wired)

### Community 81 - "Subtask Counting"
Cohesion: 0.48
Nodes (7): counted_issues(), The issues that count as items, and what was left out. Returns `(kept,…, 1.52.0 — Subtasks were counted as items everywhere, 1.53.0 — An issue-type filter that changes what is counted, A parent and its subtasks are one item, A parent and its subtasks are one item, countedIssues()

### Community 82 - "Intake Glossary"
Cohesion: 0.33
Nodes (7): Ask, Band, Candidate, Epic, Reference class, Sizing method, T-shirt scale

### Community 83 - "Jira Token Transport"
Cohesion: 0.29
Nodes (4): need_requests(), The original path: a personal API token over HTTP basic auth. Still here, still…, The dependency, or the sentence that says how to get it., _TokenTransport

### Community 84 - "CI Workflow & Parity Suite"
Cohesion: 0.33
Nodes (6): CI build & test workflow, dist/ staleness check, Actions pinned to majors, WebAssembly parity CI step, 1.76.2 — A sixth suite: the same Python under WebAssembly, byte for byte, A sixth suite: Pyodide answer equals native byte for byte

### Community 85 - "Candidate Asks Mirror"
Cohesion: 0.53
Nodes (6): Candidacy is decided in the resolver, costing a JS mirror, reattach(), asksFromIssues(), candidateAnswer(), candidateIssues(), tshirtAnswer()

### Community 86 - "Bundle Sequencing"
Cohesion: 0.33
Nodes (5): Sequencing was blocked on what an ask is inside Jira, load_asks(), Every recorded ask for one board. Read per request rather than cached: an ask…, What each ordering of this board's outstanding asks costs the others. Same tool…, sequence_for()

### Community 87 - "Window Forecast Tests"
Cohesion: 0.33
Nodes (6): A flow board's contexts and issues, one copy of the issue set per window. That…, The Monte Carlo tile, on a board whose contexts overlap. `team_slice()` gathers…, ADR 0011 has to hold in the forecaster as much as on the page. A window's…, test_a_window_is_not_a_deadline_to_the_forecaster(), test_the_forecaster_counts_one_issue_once(), _window_bundle()

### Community 88 - "Items Not Points Glossary"
Cohesion: 0.40
Nodes (5): Forecasting rules, Forecasts are in items, never story points, Issue, Item, Point

### Community 89 - "Calibration Notes"
Cohesion: 0.40
Nodes (5): calibration_note(), _narrow_sentence(), What a reader is told above a calibration score, or instead of one. The…, What is said when this reader's view was too narrow to publish. Silent when it…, 1.46.0 — The forecast log is the board's too

### Community 90 - "Team Load Glossary"
Cohesion: 0.40
Nodes (5): Commitment recommendation, Interruption rate, Throughput, Unplanned work, Work in progress

### Community 91 - "Window & Preset Helpers"
Cohesion: 0.40
Nodes (5): isWindow(), M_FLOW(), presetOfKind(), reapplyPresetForBoard(), selectableContexts()

### Community 92 - "Forecast Claims"
Cohesion: 0.50
Nodes (4): claim_id(), claims_from(), Deterministic, so re-publishing the same forecast does not duplicate it. A…, The falsifiable claims one published capacity forecast makes. `capacity` is…

### Community 93 - "Recipient Validator Parity"
Cohesion: 0.50
Nodes (4): js_problems_for(), `problemsIn` from forge/src/recipients.js, over one config., `recipients.js` and `serve_live.recipient_problems` are one rule, twice. That…, test_the_two_recipient_validators_agree()

### Community 94 - "Two Transports Parity Test"
Cohesion: 0.50
Nodes (4): What `scripts/serve_live.py` really puts on the wire, for both routes. The…, One contract, two transports. The page reaches live mode either over a same-…, _serve_live_bodies(), test_the_two_transports_answer_the_same_shape()

### Community 95 - "Series Refusal Checks"
Cohesion: 0.50
Nodes (4): The durable sprint series — ADR 0015, roadmap item 4. Two halves, and the split…, Whether a route refused. Reported by exception type, not by grepping a sentence…, _refuses(), series_checks()

## Ambiguous Edges - Review These
- `clean_dataset()` → `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md · relation: references
- `clean_dataset()` → `People picker searches by name, stores the id, projects to an allow-list of fields`  [AMBIGUOUS]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md · relation: semantically_similar_to
- `size_stability()` → `size_stability(): the interchangeable-items assumption is checked`  [AMBIGUOUS]
  docs/adr/0006-forecast-in-items-not-points.md · relation: references

## Knowledge Gaps
- **287 isolated node(s):** `SLOT`, `S`, `CARRIES_A_FIGURE`, `input`, `MAIL_CONFIG` (+282 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 647 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `clean_dataset()` and `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `clean_dataset()` and `People picker searches by name, stores the id, projects to an allow-list of fields`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **What is the exact relationship between `size_stability()` and `size_stability(): the interchangeable-items assumption is checked`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `CLAUDE.md working constraints` connect `CLAUDE.md Constraints & ADR Index` to `Organisation Config & Candidacy`, `Early Forge Changelog & A11y Suite`, `Import Pipeline`, `Hosted Calculator (Retired)`, `Calculator Retirement (ADR 0031)`, `Manifest & Business Value Field`, `Browser Suites & Early Forge History`, `Roadmap & Brief Delivery History`, `Manifest Hostnames & Realms`, `Forge Runbooks`, `Agent Skill & Templates`, `Brief Access & Permission ADRs`, `Durable Series ADRs`, `Refusal Thresholds`, `Units & Size Stability`, `README & Agent Principles`, `Intake Demo Generator`, `Architecture & One Implementation`, `Subtask Counting`, `Items Not Points Glossary`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `ADR 0008: If we ship on Forge, Forge calls a hosted calculator` connect `Foundational ADRs` to `Service Contract Tests`, `Intake Sizing`, `Page Shell & Org Config Docs`, `Manifest Hostnames & Realms`, `Sequencing & Value Basis Field`, `Hosted Calculator (Retired)`, `Dashboard Forecast Rendering`, `Facts Pack Metrics`, `Jira OAuth Login`, `Calculator Retirement (ADR 0031)`, `Security Suite`, `Live Mode Server`, `Monte Carlo Forecaster`, `Forecast Build & Commitment`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `ADR 0031 — The forecast runs inside the Forge function, and the calculator is retired` connect `Calculator Retirement (ADR 0031)` to `Foundational ADRs`, `Service Contract Tests`, `Forge Async Jobs`, `Runtime Asset Packer`, `Hosted Calculator (Retired)`, `Architecture & One Implementation`, `Bridge Adapter & Forge README`, `CLAUDE.md Constraints & ADR Index`, `CI Workflow & Parity Suite`, `Manifest & Business Value Field`, `In-function Python Runtime`, `Manifest Hostnames & Realms`, `Forge Runbooks`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **What connects `SLOT`, `S`, `CARRIES_A_FIGURE` to the rest of the system?**
  _287 weakly-connected nodes found - possible documentation gaps or missing edges._