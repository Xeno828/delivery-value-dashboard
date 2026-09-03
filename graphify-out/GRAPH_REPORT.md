# Graph Report - delivery-value-dashboard  (2026-09-03)

## Corpus Check
- 2 files · ~464,580 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2006 nodes · 4546 edges · 122 communities (102 shown, 19 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 309 edges (avg confidence: 0.71)
- Token cost: 304,800 input · 0 output

## Community Hubs (Navigation)
- Weekly Brief Composition
- Forge Resolver & Runbook
- Changelog, Manifest & Runbooks
- Browser Suites & Early Forge History
- Forge Async Jobs
- Roadmap & Permission ADRs
- ADR Index & Later ADRs
- Agent Tool Tests
- Hosted Calculator (Retired)
- Jira Issue Normalisation
- Monte Carlo Forecaster
- Import Wizard Screens
- Import Pipeline
- Forge Context & Audit Shapes
- Root Package & Flow Glossary
- Jira OAuth Login
- Service Contract Checks
- Security Suite
- Selection, Subtasks & Value Sets
- Dashboard Forecast Rendering
- Facts Pack Metrics
- Runs on Atlassian Research
- Dashboard Charts & Drilldowns
- Dashboard Org Config Mirror
- Calculator Retirement (ADR 0031)
- Forge Package Dependencies
- Routes Projection & Refusals
- Intake Ask 030
- WASM Parity & CI Suites
- Dashboard Screenshot
- Route Migration Tests
- Intake Ask 014
- Intake Ask 015
- Delivery Data Fetcher
- Dashboard Context Loading
- Agent Skill & Templates
- Bridge Adapter & Transports
- Jira Client Fields
- Tile Picker & Presets
- Intake Forecasting
- Durable Series
- Intake Ask 016
- Runtime Asset Packer
- In-function Python Runtime
- CLAUDE.md Constraints & ADR Index
- Brief Access & Permission ADRs
- Org Config & Flow Health Docs
- Live Mode Server
- Issue Selection & Slicing
- Bundle Backend
- Live Jira Backend
- Sequencing Without Scores
- Foundational ADRs & Forge README
- Live Series Server
- Intake Glossary
- Intake Sizing
- Sample Bundle & History Rows
- Working Day Calendar
- README & Agent Principles
- Context Picker Screenshot
- Forecast Log & Claims
- Status Categories
- Refusal Thresholds
- Connection Probe
- Candidate Asks Mirror
- WASM Test Harness
- Intake Simulation
- Kanban Window ADR
- Window & Rollup Rendering
- Brief Recipients UI
- Contexts & Live Mode Docs
- Tools Compute Principle
- Refuse Rather Than Widen
- Service Computes Nothing Tests
- Early Dashboard Releases
- Data Format & Dashboard Review
- Dashboard Review & No People Metrics
- Demo & Burndown Scripts
- History Series
- Config Merge & Load
- Units & Size Stability
- Config Validation
- Candidacy Answers
- Routes & Sequence Check
- Import Wizard Concepts
- Jira Token Transport
- Burndown Rebuild Script
- Page Shell & Tile Cards
- Fetcher Verification & Refresh
- Architecture & One Implementation
- Window Forecast Tests
- Items Not Points Glossary
- Team Load Glossary
- Intake Demo Generator
- Demo Bundle Generator
- Forecast Claims
- Performance Suite
- Items Not Points ADR
- Recipient Validator Parity
- Two Transports Parity Test
- Series Refusal Checks
- Iframe Pyodide Option
- Queue Cost Scenarios
- Cross-team Checks
- Forecast Log Checks
- Permission Mirroring Checks
- Field Lists Agree Test
- Footer Accounting Test
- Raw Transitions Test
- Brief Figure Guard Test
- LLM Module Match Test
- Brief Prompt Test
- Jira Read Auth Test
- Value Basis Checks
- Ageing
- Risk Register
- Scope Growth
- Value Basis
- Intake Reproducibility
- Intake Blind Spots
- Pinned Residency

## God Nodes (most connected - your core abstractions)
1. `CLAUDE.md working constraints` - 72 edges
2. `Forge app manifest` - 65 edges
3. `ADR 0031 — The forecast runs inside the Forge function, and the calculator is retired` - 54 edges
4. `check()` - 48 edges
5. `render()` - 42 edges
6. `Finishing the Forge route — runbooks` - 41 edges
7. `Hosting the calculator (retired 2026-09-03)` - 38 edges
8. `sequence()` - 35 edges
9. `Decision records index` - 35 edges
10. `ADR 0008: If we ship on Forge, Forge calls a hosted calculator` - 34 edges

## Surprising Connections (you probably didn't know these)
- `People picker searches by name, stores the id, projects to an allow-list of fields` --semantically_similar_to--> `clean_dataset()`  [AMBIGUOUS] [semantically similar]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md → service/routes.py
- `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)` --references--> `clean_dataset()`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md → service/routes.py
- `Commitment recommendation` --references--> `recommend_commitment()`  [INFERRED]
  CONTEXT.md → agent/tools/forecast.py
- `size_stability(): the interchangeable-items assumption is checked` --references--> `size_stability()`  [AMBIGUOUS]
  docs/adr/0006-forecast-in-items-not-points.md → agent/tools/forecast.py
- `Calibration` --references--> `score_calibration()`  [INFERRED]
  CONTEXT.md → agent/tools/forecast.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Calculator retirement under ADR 0031 (1.75.0 to 1.78.2)** — changelog_1_75_0, changelog_1_75_1, changelog_1_76_0, changelog_1_76_1, changelog_1_76_2, changelog_1_77_0, changelog_1_77_1, changelog_1_77_2, changelog_1_77_3, changelog_1_77_4, changelog_1_77_5, changelog_1_78_0, changelog_1_78_1, changelog_1_78_2 [EXTRACTED 1.00]
- **The phantom Forge iframe scrolling bug (1.29.1 to 1.29.5)** — changelog_1_29_1, changelog_1_29_2, changelog_1_29_3, changelog_1_29_4, changelog_1_29_5 [EXTRACTED 1.00]
- **Roadmap item 3, the scheduled brief, from decision to delivery (1.24.0 to 1.32.0)** — changelog_1_24_0, changelog_1_25_0, changelog_1_25_1, changelog_1_25_2, changelog_1_26_0, changelog_1_27_0, changelog_1_28_0, changelog_1_29_0, changelog_1_30_0, changelog_1_31_0, changelog_1_32_0 [INFERRED 0.85]
- **One implementation of every figure, held by byte-for-byte parity** — claude_agent_never_does_arithmetic, claude_nothing_between_tools_and_reader_does_arithmetic, docs_adr_0031_the_forecast_runs_inside_the_forge_function_one_implementation_of_every_figure, service_readme_routes_compute_nothing, tests_test_wasm, tests_test_service, docs_adr_0005_tools_compute_the_agent_narrates [INFERRED 0.85]
- **Refusal family: below the evidence, say the evidence is absent rather than print a plausible figure** — docs_adr_0007_refuse_rather_than_widen_refuse_rather_than_widen, docs_adr_0007_refuse_rather_than_widen_evidence_absent_not_noisy, docs_adr_0010_an_empty_selection_is_a_refusal_empty_selection_refusal, docs_adr_0011_a_kanban_context_is_a_window_not_a_clock_window_not_a_clock, docs_adr_0013_the_brief_is_written_inside_the_tenant_refusals_not_passed_through_model, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_refusal_not_a_claim [EXTRACTED 1.00]
- **Allow-list projection: stores and payloads hold named fields only, never issue text or contact details** — docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_scope_allow_list, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_people_picker_allow_list, docs_adr_0015_a_durable_series_stores_what_jira_forgets_counts_never_issue_text, docs_adr_0017_a_forecast_is_logged_as_a_count_not_a_promise_claim_fields_allow_list, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_app_store_inventory, docs_adr_0021_the_audit_log_is_operational_and_says_so_audit_entry_allow_list [INFERRED 0.85]
- **Roadmap item 5: permission mirroring, its three exposures and their accepted answers** — docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_permission_mirroring_by_asuser, docs_adr_0018_permission_mirroring_holds_by_accident_and_where_it_does_not_three_exposures, docs_adr_0019_a_recorded_row_is_a_fact_about_the_board_row_belongs_to_board, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_anchor_issue_access_control, docs_adr_0014_jira_sends_the_brief_and_the_read_only_rule_bends_restrict_browse, docs_adr_0013_the_brief_is_written_inside_the_tenant_asapp_reversal, docs_adr_0020_the_anchor_issue_is_the_brief_s_access_control_offline_user_impersonation_deferred [EXTRACTED 1.00]
- **Decisions driven by the credible-wrong-number failure class** — docs_adr_0023_a_cross_team_rollup_spans_what_the_reader_can_see_rollup_does_not_forecast, docs_adr_0024_a_parent_and_its_subtasks_are_one_piece_of_work_count_subtasks, docs_adr_0026_items_and_value_are_counted_from_two_different_sets_two_sets_items_and_value, docs_forecasting_agent_reporting_scope_is_not_forecasting_scope [INFERRED 0.85]
- **The async job path: resolver pushes, consumer computes, adapter polls** — forge_manifest_function_simulation_fn, forge_manifest_consumer_simulation_consumer, forge_src_jobs, docs_adr_0031_the_forecast_runs_inside_the_forge_function_job_row, docs_adr_0031_the_forecast_runs_inside_the_forge_function_retry_guard, forge_bridge_bridge, docs_adr_0031_the_forecast_runs_inside_the_forge_function_payload_chunks_in_app_storage [INFERRED 0.85]
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

## Communities (122 total, 19 thin omitted)

### Community 0 - "Weekly Brief Composition"
Cohesion: 0.06
Nodes (65): 1.27.0 — The brief is an email now, and the send is written and proved against stubs, 1.30.0 — Item 3 runs end to end against a real tenant, and the only thing between it and an inbox is a site setting, ADR-0005, ADR-0007, ADR-0014, People picker searches by name, stores the id, projects to an allow-list of fields, briefMessages(), composeBrief() (+57 more)

### Community 1 - "Forge Resolver & Runbook"
Cohesion: 0.07
Nodes (51): 1.29.0 — The scheduled brief reads the board and sends it; item 3 is built end to end, 1.77.1 — The facts route is answered inside the Forge function, 1.77.2 — The forecast is answered inside the Forge function, 1.77.3 — The forecast is a job, because the forecast on a real board does not fit a resolver call, 1.77.4 — The trend series is answered inside the Forge function, 1.77.5 — The burndown is answered inside the Forge function, and nothing reaches the calculator any more, ADR-0008, ADR-0009 (+43 more)

### Community 2 - "Changelog, Manifest & Runbooks"
Cohesion: 0.07
Nodes (57): 1.18.0 — The calculator can authenticate a tenant, 1.18.1 — The token verifier raised where it should have refused, and CI found it on the first push, 1.19.0 — The hosted calculator has a plan, and writing it found that forge-token was never blocked only on four values, 1.20.0 — The calculator has somewhere to be deployed from, and nothing on the way there holds a key, 1.20.1 — The calculator is deployed and serving in us-central1, and the first deploy reported it as dead, 1.20.2 — The calculator is hosted, 1.20.3 — The cold start is measured rather than feared, 1.21.0 — The calculator is tenant-aware in production (+49 more)

### Community 3 - "Browser Suites & Early Forge History"
Cohesion: 0.06
Nodes (48): CI build & test workflow, dist/ staleness check, Actions pinned to majors, WebAssembly parity CI step, GitHub Pages publish job, build(), build_split(), main() (+40 more)

### Community 4 - "Forge Async Jobs"
Cohesion: 0.06
Nodes (48): ADR-0017, ADR-0018, The job row, consumer simulation-consumer (queue simulations), chunkPayload(), collect(), CONSUMER_ROUTES, FAILED_SENTENCE (+40 more)

### Community 5 - "Roadmap & Permission ADRs"
Cohesion: 0.09
Nodes (50): Score past forecasts against what actually happened. Without this the agent is…, score_calibration(), 1.40.2 — docs/roadmap.md records item 4 as part done, and defines the letters the entries below have been using, 1.41.0 — The forecaster can be scored against its own history now, for the first time, 1.42.0 — The forecast log is wired, and the forecaster is falsifiable for the first time, 1.43.0 — The trend window is a setting, and both of its truncations now say what they cut; roadmap item 4 is done, 1.44.0 — Roadmap item 5 is started, and it starts by finding two exposures this repository created yesterday, 1.45.0 — A recorded sprint row belongs to the board, and that decision has teeth (+42 more)

### Community 6 - "ADR Index & Later ADRs"
Cohesion: 0.08
Nodes (48): One issue's business value as it should be counted, or zero. The one place the…, value_of(), 1.54.0 — The app declares a Business Value field, so a Forge tenant can report value for the first time, 1.57.0 — The app declares a Value Basis field, and it is free text on purpose, 1.57.1 — The cost stated in 1.57.0 was wrong, and the deploy is what said so, 1.62.0 — The fetcher reads the two fields this app declares, and fetches the issues that carry them, 1.63.0 — Something in Jira can now say 'this is being weighed against other things', 1.64.0 — The Forge build had lost the coloured half of itself, and it looked like a design decision (+40 more)

### Community 7 - "Agent Tool Tests"
Cohesion: 0.07
Nodes (47): check(), _intake_ds(), near(), An unauthenticated pull must stop, not degrade — found against live Jira.…, The facts pack reports the sprint; the forecaster uses all history. Conflating…, `/rest/api/3/search` was removed; `/search/jql` pages by token. Not a URL swap.…, The three ways a forecast can be built from the wrong slice of the file. All…, The headline output: is the range driven by not knowing the size, or by normal… (+39 more)

### Community 8 - "Hosted Calculator (Retired)"
Cohesion: 0.05
Nodes (47): 1.78.0 — The remote is gone, and with it the calculator: every figure is computed inside the Forge function, New module type or scope change is major; another entry under a declared block is not, No silent caps, ADR 0012 — The calculator is reached by invokeRemote (superseded), What invokeRemote costs, Region pinning resolved by Forge per install, Rejected: bearer secret over plain fetch, Rejected: an IP allow-list as access control (+39 more)

### Community 9 - "Jira Issue Normalisation"
Cohesion: 0.06
Nodes (45): ADR-0011, ADR-0024, ADR-0025, ADR-0026, ADR-0027, ADR-0029, No text from the page reaches Jira, The resolver plays the fetcher's part, not the calculator's (+37 more)

### Community 10 - "Monte Carlo Forecaster"
Cohesion: 0.10
Nodes (41): add_working_days(), build(), CountForecast, cycle_times(), _d(), DateForecast, forecast_completion(), forecast_count_by_date() (+33 more)

### Community 11 - "Import Wizard Screens"
Cohesion: 0.06
Nodes (42): Import mapping screenshot, Assignee field, Auto-detected mapping (green check status), Burndown and completion, Column mapping table (Dashboard field / Your column / Example value / Status), Connect Jira / Asana tab, Created date field (drives ageing and lead time), Custom field mapping (story points, started date) (+34 more)

### Community 12 - "Import Pipeline"
Cohesion: 0.08
Nodes (36): Import problem issue template, UI colour tokens are separate from the chart palette, Built file makes zero network calls and uses zero browser storage, Adding an import format, Charts follow the colour rules, Derived data is recomputed, never inherited, Every chart has a table view, Every number traces to issues (+28 more)

### Community 13 - "Forge Context & Audit Shapes"
Cohesion: 0.07
Nodes (38): 1.69.1 — The value tile stops guessing, 1.70.0 — A key a producer emits and no consumer takes is now a failing test, 1.71.0 — A tile said the wrong thing about a board where it was working correctly, and a refusal disproved itself in its own sentence, ADR-0021, ADR-0028, problemsInAuditEntry: counts, flags, field names, one actor identity, appendAudit(), AUDIT_EVENTS (+30 more)

### Community 14 - "Root Package & Flow Glossary"
Cohesion: 0.06
Nodes (35): Board, Bundle, Cumulative flow, Cycle time, Flow board, Flow health, Health score, Lead time (+27 more)

### Community 15 - "Jira OAuth Login"
Cohesion: 0.10
Nodes (25): The personal API token path lives only in scripts/, Connecting Jira and Asana, Fetcher with an API token (scripts/fetch_delivery_data.py), MCP connectors and CSV export routes, OAuth 2.0 (3LO) route via scripts/jira_auth.py, OAuth 2.0 (3LO) for a Jira that is not your own, accessible_resources(), authorize_url() (+17 more)

### Community 16 - "Service Contract Checks"
Cohesion: 0.06
Nodes (35): ask_assembly_checks(), audit_log_checks(), body_keys_reach_a_reader(), business_value_checks(), check(), counting_checks(), A Forge Custom UI iframe blocks inline <style> and <script>, silently. The page…, A flow board's window must be one object, not two that look alike. A board that… (+27 more)

### Community 17 - "Security Suite"
Cohesion: 0.11
Nodes (33): 1.31.0 — The recipient picker takes a name, not an account id, 1.32.0 — A brief was delivered; roadmap item 3 is done, 1.33.0 — The recipient field shows who those ids are, 1.34.0 — The account-ID field is folded away, and the named list is where recipients are edited, 1.9.1 — The live-mode server dropped the connection on any 404 instead of sending it, 1.9.2 — The source badge denied live connections that were working, Credentials live only in the fetcher's environment, ADR 0001: The dashboard is one self-contained HTML file (+25 more)

### Community 18 - "Selection, Subtasks & Value Sets"
Cohesion: 0.09
Nodes (33): counted_issues(), The issues that count as items, and what was left out. Returns `(kept,…, Whether this issue's business value is counted — ADR 0025. Value belongs at one…, The issues whose business value is counted — the *other* pool. Items and value…, value_counts(), value_issues(), forecast_for(), Run the real forecaster for one context. Returns None for an unknown id. The… (+25 more)

### Community 19 - "Dashboard Forecast Rendering"
Cohesion: 0.10
Nodes (26): 1.16.10 — Cycle time works inside a Jira tenant, 1.16.11 — A board with no sprints shows the tiles that measure it, and not the three that never can, 1.16.9 — The risk register was reporting a clean bill of health over rules it never ran, ADR-0004, ADR-0023, bindForecastInputs(), fcKey(), fcRefusal() (+18 more)

### Community 20 - "Facts Pack Metrics"
Cohesion: 0.10
Nodes (29): burndown(), _d(), diff(), elapsed_days(), facts(), _get(), in_sprint(), is_done() (+21 more)

### Community 21 - "Runs on Atlassian Research"
Cohesion: 0.09
Nodes (27): Epic grouping field chosen once for the whole set, What counts as a finished epic, The sizing ladder (tshirt / reference-class / explicit), T-shirt sizes calibrated per board, Async event at-least-once delivery and retries, Consumer function limits: 900 s, 1,024 MB, Forge consumer module, Forge Realtime as an alternative to polling (+19 more)

### Community 22 - "Dashboard Charts & Drilldowns"
Cohesion: 0.19
Nodes (25): Drill-down, Adding a metric, cycleRows(), drawTable(), littlesLaw(), openDrill(), pctile(), renderAge() (+17 more)

### Community 23 - "Dashboard Org Config Mirror"
Cohesion: 0.13
Nodes (24): 1.59.0 — The page dropped four of the organisation's own settings and used its defaults instead, 1.60.0 — The dashboard now says which statuses its config did not name, 1.61.0 — A reader who knows the board can now say what each status means, applyWorkflow(), boardStatuses(), buildView(), contextWorkingDays(), countedIssues() (+16 more)

### Community 24 - "Calculator Retirement (ADR 0031)"
Cohesion: 0.08
Nodes (24): Calculator, ADR 0031 — The forecast runs inside the Forge function, and the calculator is retired, Budget: 900 seconds and 1,024 MB, The event carries the projection, Corrected 2026-09-03: the forecast is asynchronous too, Resolver loads from a memory snapshot; the consumer does not, Forecast payload travels through app storage in chunks, Rejected: caching a result by board and dataset (+16 more)

### Community 25 - "Forge Package Dependencies"
Cohesion: 0.08
Nodes (23): esbuild, @forge/api, @forge/bridge, @forge/events, @forge/kvs, @forge/llm, dependencies, @forge/api (+15 more)

### Community 26 - "Routes Projection & Refusals"
Cohesion: 0.20
Nodes (21): 1.76.0 — The calculator's answers are one module, and the socket in front of them is another, Exception, check_sequence(), clean_dataset(), _clean_issue(), _iso_or_none(), A bad request, with the sentence to send back., The dataset the tools will see, or a refusal saying what was wrong. (+13 more)

### Community 27 - "Intake Ask 030"
Cohesion: 0.09
Nodes (22): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+14 more)

### Community 28 - "WASM Parity & CI Suites"
Cohesion: 0.16
Nodes (21): A sixth suite: Pyodide answer equals native byte for byte, _intake_bodies(), project(), The measurement the architecture is built on, asserted rather than recalled.…, The demo intake bundle, projected, and its asks stripped of every word. What…, A different calendar is a different answer — including, sometimes, no answer., One team's slice, projected — exactly what the Forge resolver sends., team_payload() (+13 more)

### Community 29 - "Dashboard Screenshot"
Cohesion: 0.11
Nodes (22): Dashboard screenshot (Sprint 24 — delivery and value), Burndown with scope changes shown, Business value delivered ($34,800 estimated, with stated basis), Can we trust the forecast? (committed vs completed, last six sprints), How long work takes and how much is waiting (flow efficiency per closed item), Every figure traces back to an issue (footer principle, click-through links), Filter row (Source, Project, Board, Sprint, Person, Epic, Type, Status, Find), Flow efficiency (32% of elapsed time was active work) (+14 more)

### Community 30 - "Route Migration Tests"
Cohesion: 0.13
Nodes (20): 1.78.1 — The hosted service's own files go, 1.78.2 — A test that held the migration's overlap has nothing left to overlap, _code_only(), _manifest_item(), `kind` is carried on the wire, by both transports, on every entry. ADR 0011…, The scalar fields of the manifest list item introduced by `- key: <key>`. Regex…, A scheduled trigger is not a resolver call, and the manifest said it was.…, A Forge reader gets the chart a file reader gets, from the same function. Two… (+12 more)

### Community 31 - "Intake Ask 014"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 32 - "Intake Ask 015"
Cohesion: 0.10
Nodes (20): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+12 more)

### Community 33 - "Delivery Data Fetcher"
Cohesion: 0.18
Nodes (19): Started date lives in the changelog, not the export, asana_pull(), build_burndown(), configure(), connect_jira(), d(), jira_bundle(), jira_pull() (+11 more)

### Community 34 - "Dashboard Context Loading"
Cohesion: 0.16
Nodes (20): commitU(), fetchSeries(), filtered(), loadContext(), loadRollupMembers(), orgSummary(), probeLive(), refreshLive() (+12 more)

### Community 35 - "Agent Skill & Templates"
Cohesion: 0.15
Nodes (19): Sprint 24 delivery brief (worked example), Sprint 24 team report (worked example), delivery-report agent skill, Evidence tagging, Prohibited outputs, Agent refusal thresholds, Agent sequence: load, diff, forecast, reconcile, write, log, score, Exec brief template (+11 more)

### Community 36 - "Bridge Adapter & Transports"
Cohesion: 0.15
Nodes (16): 1.16.0 — The dashboard inside Forge shows the customer's own Jira, not a demo company's, 1.16.1 — The dashboard scored an empty sprint 66 out of 100, 1.16.2 — Reconciled with the per-site calendar work, which landed on main in parallel, 1.28.0 — Each board now has its own recipients, set from the dashboard by a project administrator, Live mode has two transports and one set of body shapes, Live mode, ADR 0009: One contract, two transports, Forge bridge adapter (window.__DVD_BRIDGE__) (+8 more)

### Community 37 - "Jira Client Fields"
Cohesion: 0.15
Nodes (9): Jira, The Jira surface this script needs, over either transport. `url` is the…, Who this connection is authenticated as — `(identity, None)`, or `(None, why)`…, Locate the story-point and sprint custom fields by display name., The field that says an issue is an ask — ours, or the site's own. `"app"` is…, The field carrying an ask's t-shirt band — ours, or the site's own. Same rule…, This app's own Business Value and Value Basis fields on this site. **Matched on…, The board's epics as issues — ADR 0026. **Epics are not on a scrum board.**… (+1 more)

### Community 38 - "Tile Picker & Presets"
Cohesion: 0.18
Nodes (19): announcePicker(), applyOrder(), applyTiles(), buildPicker(), buildPickerList(), download(), focusMover(), moveTile() (+11 more)

### Community 39 - "Intake Forecasting"
Cohesion: 0.19
Nodes (17): Intake brief template, board_issues(), _d(), epic_sizes(), _fmt(), _fmt_sequence(), main(), queue_ahead() (+9 more)

### Community 40 - "Durable Series"
Cohesion: 0.16
Nodes (17): 1.37.0 — The durable series has a module and a shape, and neither of them stores an issue, 1.38.0 — A Forge tenant has a trend at last, ADR-0015, COMPARED, entryFrom(), isFiniteNumber(), NULLABLE, problemsInRow() (+9 more)

### Community 41 - "Intake Ask 016"
Cohesion: 0.11
Nodes (17): assumptions, dependencies, id, neededBy, problemStatement, requestedBy, sizing, basis (+9 more)

### Community 42 - "Runtime Asset Packer"
Cohesion: 0.11
Nodes (16): Generated at deploy, never committed, { BOOT, writeSources }, digest, files, hash, HERE, OUT, probe (+8 more)

### Community 43 - "In-function Python Runtime"
Cohesion: 0.18
Nodes (15): 1.76.1 — The Python runtime travels into the Forge function as a generated module, and the loader that unpacks it exists, ADR-0031, How the runtime travels, answer(), baseDir(), fs, load(), loadAssets() (+7 more)

### Community 44 - "CLAUDE.md Constraints & ADR Index"
Cohesion: 0.13
Nodes (17): CLAUDE.md working constraints, dist/ is committed on purpose, An empty selection is a refusal, not a zero, The manifest declares no remote and must not gain one, Monte Carlo is seeded and reproducible, Never compute a priority score, No hours, overtime, or timesheet field, When you change something (+9 more)

### Community 45 - "Brief Access & Permission ADRs"
Cohesion: 0.14
Nodes (17): Every Forge scope is read-only except two named ones, Superseded in part: the scheduled read takes asApp() deliberately, The file leaves: mailing is the one boundary crossing (later closed by ADR 0014), A scheduled trigger runs with no user principal, ADR 0014: Jira sends the brief, and the read-only rule bends by allow-list, forge/src/compose.js keeps the send provable without deploying, Jira sends the brief via issue notify; nothing leaves, Outgoing mail is a site setting, not a scope (+9 more)

### Community 46 - "Org Config & Flow Health Docs"
Cohesion: 0.13
Nodes (16): Flow board window context (kind: window), Flow health composite, The four flow tiles, Sprint health refuses whole on a flow board, Refuse in place versus not shown, statusTransitions sent raw by the resolver, A bad config stops the run, orgConfig Jira project property on Forge (+8 more)

### Community 47 - "Live Mode Server"
Cohesion: 0.15
Nodes (13): append_audit(), Handler, A mirror of `problemsIn` in forge/src/recipients.js, in Python. A second…, One board's forecast log. Missing and unreadable both read as empty — a caller…, Mirrors `appendAudit` in forge/src/audit.js, bound included. Best-effort and…, The one route that changes something. A POST rather than a GET with parameters,…, read_audit(), read_forecast_log() (+5 more)

### Community 48 - "Issue Selection & Slicing"
Cohesion: 0.16
Nodes (15): cross_team_boards(), cross_team_label(), cross_team_members(), Which issues a forecast reads, and what it is told about them. This is the…, The context a forecast is *for*, and the sprints a rollup stands for. Returns…, Which contexts a forecast for `cid` would sample, and how it chose them.…, Every sprint context in a project, for a cross-team roll-up. **Sprints only.**…, The boards a cross-team roll-up spans, in a stable order, by name. Names and… (+7 more)

### Community 49 - "Bundle Backend"
Cohesion: 0.13
Nodes (9): Sequencing was blocked on what an ask is inside Jira, BundleBackend, load_asks(), no_days_yet_note(), Why a sprint's chart has no day on it that has happened yet, or `None`. Mirrors…, Reads an existing bundle file. Used for demos, tests, and for working offline…, Every recorded ask for one board. Read per request rather than cached: an ask…, What each ordering of this board's outstanding asks costs the others. Same tool… (+1 more)

### Community 50 - "Live Jira Backend"
Cohesion: 0.17
Nodes (8): JiraBackend, main(), Which issues are *in* a window, as a JQL predicate. The membership ADR 0011…, Queries Jira on demand. Sprint lists are cheap; issues are fetched only when a…, The saved filter behind a board, which is how plain JQL is scoped to one. The…, Sequencing sizes asks against the board's completed epics and its interruption…, Unlike the bundle, this has to fetch. A forecast needs the team's whole…, window_membership_jql()

### Community 51 - "Sequencing Without Scores"
Cohesion: 0.18
Nodes (14): The refusal sentence for more asks than one sequencing compares, or None. A…, For a set of asks against one team, what each ordering costs the others.…, sequence(), too_many_asks(), What an ask is inside Jira (open product question), A value basis is prose, never an input, GET api/sequence?id=, Value figure as a floor with a basis line per item (+6 more)

### Community 52 - "Foundational ADRs & Forge README"
Cohesion: 0.19
Nodes (14): 1.14.0 — Phase 1 of the commercial roadmap: make it connectable, 1.15.0 — If we ship on Forge, the forecast comes with us, ADR 0008: If we ship on Forge, Forge calls a hosted calculator, Pyodide (CPython under WebAssembly) inside the Forge function, Pyodide in the Custom UI iframe (rejected), Runs on Atlassian badge, Item 1: OAuth app on the Marketplace — done, as both routes, Risks the original names (+6 more)

### Community 53 - "Live Series Server"
Cohesion: 0.20
Nodes (13): The third part of a flow board's context id. Prefixed rather than bare, so a…, One selectable window, in the shape the sprint entry above uses. Field for…, One board's recorded rows. Missing and unreadable both read as empty. Keyed by…, Whether this observation may be written. Mirrors `recordable` in…, The trend series for the board `cid` belongs to, and the recording of it. The…, Mirrors `statusFingerprint` in `forge/src/series.js`. Order- and case-…, read_series(), series_fingerprint() (+5 more)

### Community 54 - "Intake Glossary"
Cohesion: 0.17
Nodes (13): Intake mode, Ask, Band, Candidate, Capacity scenario, Cost of the queue, Epic, Queue ahead (+5 more)

### Community 55 - "Intake Sizing"
Cohesion: 0.19
Nodes (12): Derive S/M/L/XL bands from the team's own completed epics. Quartiles, not a…, Turn a product ask into a distribution of item counts., Refusal, size_ask(), Sizing, _triangular(), tshirt_scale(), Value Basis custom field (free text) (+4 more)

### Community 56 - "Sample Bundle & History Rows"
Cohesion: 0.23
Nodes (12): history_row(), One sprint's row of the trend series, as it stood at `as_of`. **Every count…, 1.36.0 — A closed sprint got better the longer ago it was, and nothing on screen said so, First answer, corrected: wipItems re-derives correctly, build_history(), How many sprints of trend the dataset keeps. One reader, so the fetcher and…, Append this sprint to whatever history the previous file held, so the trend…, trend_window() (+4 more)

### Community 57 - "Working Day Calendar"
Cohesion: 0.26
Nodes (12): add_working_days(), counted_note(), holiday_set(), is_working_day(), `d` is a date or an ISO string., Working dates between two ISO dates or dates, inclusive. Returns `date`…, The date `n` working days after `start`, skipping holidays too., What a reader is told about issues that were not counted. Silent when nothing… (+4 more)

### Community 58 - "README & Agent Principles"
Cohesion: 0.15
Nodes (12): 1.8.1 — The Pages workflow is manual-only now, 1.8.2 — PUSH.md and scripts/setup-on-mac.sh are gone, Deploying: email, shared drive, Pages, board pack, Fetcher script for regular refreshes, The four questions activity reporting fails to answer, MCP connectors once the format has proved itself, Monte Carlo forecasting in the page, Sequence asks mode (+4 more)

### Community 59 - "Context Picker Screenshot"
Cohesion: 0.22
Nodes (13): Context picker screenshot, Board selector, Context bar (Source / Project / Board / Sprint), Data-as-at timestamp, Data bundle pill (Demo bundle - 3 boards x 6 sprints), Header line (Project · Team · Sprint dates · data as at), Project selector, Source badge (JIRA) (+5 more)

### Community 60 - "Forecast Log & Claims"
Cohesion: 0.17
Nodes (12): calibration_note(), _narrow_sentence(), problems_in_claim(), What is wrong with one logged claim, as sentences. Empty means storable.…, Score every claim whose horizon has passed, from completions in its window.…, What a reader is told above a calibration score, or instead of one. The…, What is said when this reader's view was too narrow to publish. Silent when it…, The log, bounded, oldest resolved entries first. Reports what it dropped. No… (+4 more)

### Community 61 - "Status Categories"
Cohesion: 0.20
Nodes (7): is_done(), _norm(), Maps tracker status names onto To Do / In Progress / Done. Records every name…, Status names no rule covered, in the spelling the tracker used., Every uncovered status, what it was read as, and on what evidence. Written into…, Completion, from the field the producer already resolved. Downstream tools read…, Statuses

### Community 62 - "Refusal Thresholds"
Cohesion: 0.17
Nodes (12): Refusal thresholds are hard, not advisory, Published calibration score that stops probabilities, Forecasting agent design outline, Backtest with non-overlapping windows and full horizons, Brier score over the forecast log, Agent guardrails, Reporting scope is not forecasting scope, Reporting and forecasting are two jobs with opposite failure modes (+4 more)

### Community 63 - "Connection Probe"
Cohesion: 0.32
Nodes (11): Section 1: Bridge, Connection check page (probe), Section 3: What would leave the tenant, Section 2: Reading a board by id, call(), loadBoard(), main(), note() (+3 more)

### Community 64 - "Candidate Asks Mirror"
Cohesion: 0.29
Nodes (11): asks_from_issues(), `(asks, notes)` — every declared candidate on this board, as asks. An ask has…, 1.66.0 — The Forge sequencing refusal is gone, assertAsksCarryNoText / _refuse_ask_text, Candidacy is decided in the resolver, costing a JS mirror, assertAsksCarryNoText(), reattach(), asksFromIssues() (+3 more)

### Community 65 - "WASM Test Harness"
Cohesion: 0.18
Nodes (10): assets, cases, [casesPath, outPath, modeFlag], HERE, loadMs, require, results, runtime (+2 more)

### Community 66 - "Intake Simulation"
Cohesion: 0.24
Nodes (10): attribute_uncertainty(), capacity(), forecast_ask(), interruption_rate(), _pct(), Share of each sprint that arrived after planning, averaged. Capacity available…, Throughput samples available to a new ask under one scenario., Working days until the ask itself is complete, having first cleared any queue… (+2 more)

### Community 67 - "Kanban Window ADR"
Cohesion: 0.24
Nodes (10): 1.16.4 — A dataset that stated no sprint dates was told how many items to commit to, 1.16.5 — The two transports now agree what a window is, before either one offers a board a window, 1.16.6 — A board that runs no sprints is offered something for the first time, 1.72.0 — The burndown tile has been blank on every Forge install since the bridge existed, and the sentence under it blamed the tenant's data, A single 'no data' banner and dimming were rejected, ADR 0011: A kanban context is a window, and a window is not a clock, A kanban context is a rolling window, A tile that can never say anything is not shown (+2 more)

### Community 68 - "Window & Rollup Rendering"
Cohesion: 0.22
Nodes (10): 1.16.7 — The page knows a window is not a clock, 1.16.8 — Every tile that would have stated a sprint-shaped figure on a flow board now says what it in particular cannot show, 1.9.0 — Tiles can be turned off, so one file can be sent to two audiences, contextById(), derive(), renderExec(), rollupCovers(), rollupLead() (+2 more)

### Community 69 - "Brief Recipients UI"
Cohesion: 0.27
Nodes (10): 1.35.0 — The read-only view of the recipients tile shows names too, which is the surface 1.34.0 said it had not fixed, auditHtml(), briefAudienceFields(), briefBoard(), briefList(), fetchRecipients(), renderBrief(), showBriefNames() (+2 more)

### Community 70 - "Contexts & Live Mode Docs"
Cohesion: 0.20
Nodes (10): ADR 0002: The page never queries Jira or Asana; data arrives as a bundle, Contexts fetched up front into a bundle, Live mode: local server on 127.0.0.1, The page cannot call Jira or Asana itself, Filtering by project, board and sprint (contexts and live mode), GET api/forecast?id=, Bundle format (schemaVersion 2.0), Live mode via scripts/serve_live.py (+2 more)

### Community 71 - "Tools Compute Principle"
Cohesion: 0.22
Nodes (10): ADR 0005: The tools compute; the agent only narrates, Tools compute; the agent narrates, Hosted calculator imports the Python tools unchanged, Rejected: a WSGI adapter for a function runtime, Figures enter by substitution and prose is checked for foreign numerals, Agent executive summary, Executive brief and team report from one set of facts, Rollout: shadow, team report, exec brief, automate (+2 more)

### Community 72 - "Refuse Rather Than Widen"
Cohesion: 0.24
Nodes (10): ADR 0007: Below the evidence thresholds, refuse rather than widen the interval, Refusal clause: the evidence is absent, not noisy, Refuse rather than widen the interval, An empty selection is a refusal, not a zero, Refusal sentences are inserted verbatim, not passed through the model, A refusal is not a claim, MIN_TSHIRT_EPICS = 8 (vs MIN_REFERENCE_EPICS 5), Refusal thresholds (+2 more)

### Community 73 - "Service Computes Nothing Tests"
Cohesion: 0.20
Nodes (10): call(), The service's answer is the tool's answer, to the byte., Intake's reference class, over the payload the calculator really receives.…, `service/` is `routes.py` and nothing else. ADR 0031. The hosted calculator's…, One route, answered: `(status, payload)`. The signature kept the shape of the…, A traceback carries field values, and those are the customer's., test_epic_sizing_survives_the_projection(), test_no_internals_leak() (+2 more)

### Community 74 - "Early Dashboard Releases"
Cohesion: 0.25
Nodes (9): 1.4.0 — The dashboard now measures in items by default, with a Points toggle, 1.5.0 — Project, board and sprint filtering, 1.5.1 — Performance measured rather than assumed, 1.6.0 — A shareable demo, and an executive summary of the agent, 1.7.0 — Overtime removed, Escape at output, once, Escape at output, exactly once, issueRow() (+1 more)

### Community 75 - "Data Format & Dashboard Review"
Cohesion: 0.22
Nodes (9): Context: one project + board + sprint, Data format, History rows are derived from dates at asOfDate, never current status, orgConfig.inferredStatuses, started, recovered from the changelog, Units: items by default; calendar days reported, working days simulated, Window context ids on flow boards (win:14d/30d/90d), Calendar days reported, working days simulated (+1 more)

### Community 76 - "Dashboard Review & No People Metrics"
Cohesion: 0.22
Nodes (9): Sprint 24 dashboard review, Burndown with a scope line and mid-sprint callout, Health score with the method exposed on hover, One completion figure from a single field, Predictability card with recommended next commitment, Team load card replacing output-per-person and overtime, Waiting-vs-working elapsed time chart, Burndown carries both units, always (+1 more)

### Community 77 - "Demo & Burndown Scripts"
Cohesion: 0.33
Nodes (8): Repository layout, build_cards(), forecast_json(), main(), Opening and closing cards. The closing figures come from the real forecaster…, The closing card quotes the forecaster, so the numbers on it have to come from…, run(), scenes()

### Community 78 - "History Series"
Cohesion: 0.29
Nodes (8): history_series(), One row per sprint context, in the order the board runs them. The loop lives…, 1.38.1 — The fetcher is importable again without a tracker dependency, and CI is what found it, 1.39.0 — The calculator image takes Debian's security updates at build time, and deploys move again, 1.39.1 — The trend was empty in the tenant, and the cause was a sort order, 1.39.2 — A sprint the series could not date left it silently, and the tile blamed thin data, 1.40.0 — Three things a two-sprint board made visible, 1.40.1 — The same false basis, in the next clause of the same sentence

### Community 79 - "Config Merge & Load"
Cohesion: 0.29
Nodes (8): from_dataset(), main(), merge(), Shallow-merge one level down, which is as deep as this schema goes. `statuses`…, The config a dataset was built with, or the defaults if it predates this., One line for a basis note, so a figure can name the rules behind it., summary(), The config travels inside the data

### Community 80 - "Units & Size Stability"
Cohesion: 0.33
Nodes (7): agent/SKILL.md, 1.2.0 — Reporting and forecasting agent (agent/), 1.3.0 — Item counts made the unit end to end, The agent never does arithmetic, Agent intake mode's four standing rules, Uncertainty attribution (size vs delivery), The reporting & forecasting agent

### Community 81 - "Config Validation"
Cohesion: 0.29
Nodes (7): meta.calendar must equal inputs.calendar, load(), Read and validate a config file. Exits with the problems if it is wrong.…, Every problem with a config, as sentences. Empty list means usable., validate(), The organisation config travels inside the data, never beside it, Telling it what done means

### Community 82 - "Candidacy Answers"
Cohesion: 0.29
Nodes (7): candidate_answer(), candidate_issues(), `None`, a band, or the unrecognised string somebody actually wrote. Three…, What the candidacy field says: `None`, `True`, `False`, or the words. Four…, `(asks, unreadable)` — the candidates, and the answers nobody can read. An ask…, tshirt_answer(), candidate_answer: None / True / False / str

### Community 83 - "Routes & Sequence Check"
Cohesion: 0.29
Nodes (7): 1.76.2 — A sixth suite: the same Python under WebAssembly, byte for byte, 1.77.0 — Sequencing runs inside the Forge function, as a job, and the page cannot tell, Architecture in one paragraph, answer(), Everything `/v1/sequence` would refuse, and nothing it would compute. The Forge…, One route's envelope: `(status, payload)`, no socket and no auth. This is the…, route_sequence_check()

### Community 84 - "Import Wizard Concepts"
Cohesion: 0.33
Nodes (7): Added-mid-sprint inferred from created date, All-numeric date disambiguation, Column mapping by synonym list, Import wizard (Load data), Burndown and history row recomputed on upload, Replace or merge apply modes, Load data modal (#modal), three steps

### Community 85 - "Jira Token Transport"
Cohesion: 0.29
Nodes (4): need_requests(), The original path: a personal API token over HTTP basic auth. Still here, still…, The dependency, or the sentence that says how to get it., _TokenTransport

### Community 86 - "Burndown Rebuild Script"
Cohesion: 0.52
Nodes (6): _d(), in_sprint(), main(), Same rule as the facts pack: in scope unless finished before the start., rebuild(), working_days()

### Community 87 - "Page Shell & Tile Cards"
Cohesion: 0.29
Nodes (7): Brief recipients card (#c-brief), Build placeholders @@STYLES@@ @@SEED@@ @@APP@@ @@IMPORT@@, Filter bar: person, epic, types, status, find, measure, Flow tile cards: c-cycle, c-wip, c-thr, c-cfd, Issue drill-down panel (#panel), Dashboard page shell (src/index.html), Tile grid (#grid)

### Community 88 - "Fetcher Verification & Refresh"
Cohesion: 0.33
Nodes (5): 1.58.0 — The fetcher made its first real request to a Jira, and three things were wrong that no stub could have shown, 1.58.1 — Accepted is stated rather than inferred, Prove the connection is somebody, before a single figure is pulled. The check…, _verified(), refresh.sh script

### Community 89 - "Architecture & One Implementation"
Cohesion: 0.33
Nodes (6): Nothing between the tools and a reader may do arithmetic, One implementation of every figure, service/ README, The directory is named for what used to be beside routes.py, Anything added must import under Pyodide, routes.py computes nothing

### Community 90 - "Window Forecast Tests"
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

### Community 95 - "Forecast Claims"
Cohesion: 0.50
Nodes (4): claim_id(), claims_from(), Deterministic, so re-publishing the same forecast does not duplicate it. A…, The falsifiable claims one published capacity forecast makes. `capacity` is…

### Community 96 - "Performance Suite"
Cohesion: 0.67
Nodes (3): The suites CI enforces, main(), run()

### Community 97 - "Items Not Points ADR"
Cohesion: 0.67
Nodes (4): ADR 0006: Forecasts count items, never story points, Forecasts count items, never story points, size_stability(): the interchangeable-items assumption is checked, Monte Carlo over item throughput, 20,000 seeded trials

### Community 98 - "Recipient Validator Parity"
Cohesion: 0.50
Nodes (4): js_problems_for(), `problemsIn` from forge/src/recipients.js, over one config., `recipients.js` and `serve_live.recipient_problems` are one rule, twice. That…, test_the_two_recipient_validators_agree()

### Community 99 - "Two Transports Parity Test"
Cohesion: 0.50
Nodes (4): What `scripts/serve_live.py` really puts on the wire, for both routes. The…, One contract, two transports. The page reaches live mode either over a same-…, _serve_live_bodies(), test_the_two_transports_answer_the_same_shape()

### Community 100 - "Series Refusal Checks"
Cohesion: 0.50
Nodes (4): The durable sprint series — ADR 0015, roadmap item 4. Two halves, and the split…, Whether a route refused. Reported by exception type, not by grepping a sentence…, _refuses(), series_checks()

### Community 101 - "Iframe Pyodide Option"
Cohesion: 0.67
Nodes (3): Pyodide in the Custom UI iframe, unsafe-eval CSP option for WebAssembly, scheduledTrigger weekly-brief (week)

## Ambiguous Edges - Review These
- `clean_dataset()` → `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`  [AMBIGUOUS]
  docs/adr/0013-the-brief-is-written-inside-the-tenant.md · relation: references
- `clean_dataset()` → `People picker searches by name, stores the id, projects to an allow-list of fields`  [AMBIGUOUS]
  docs/adr/0014-jira-sends-the-brief-and-the-read-only-rule-bends.md · relation: semantically_similar_to
- `size_stability()` → `size_stability(): the interchangeable-items assumption is checked`  [AMBIGUOUS]
  docs/adr/0006-forecast-in-items-not-points.md · relation: references

## Knowledge Gaps
- **283 isolated node(s):** `ASK_TEXT_FIELDS`, `CALC_FIELDS`, `_epics`, `orgConfigs`, `RECIPIENTS_KEY` (+278 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 644 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `clean_dataset()` and `The file leaves: mailing is the one boundary crossing (later closed by ADR 0014)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `clean_dataset()` and `People picker searches by name, stores the id, projects to an allow-list of fields`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **What is the exact relationship between `size_stability()` and `size_stability(): the interchangeable-items assumption is checked`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **Why does `CLAUDE.md working constraints` connect `CLAUDE.md Constraints & ADR Index` to `Changelog, Manifest & Runbooks`, `Roadmap & Permission ADRs`, `ADR Index & Later ADRs`, `Hosted Calculator (Retired)`, `Import Pipeline`, `Security Suite`, `Selection, Subtasks & Value Sets`, `Dashboard Org Config Mirror`, `Calculator Retirement (ADR 0031)`, `Route Migration Tests`, `Agent Skill & Templates`, `Bridge Adapter & Transports`, `Brief Access & Permission ADRs`, `Foundational ADRs & Forge README`, `README & Agent Principles`, `Refusal Thresholds`, `Kanban Window ADR`, `Early Dashboard Releases`, `History Series`, `Units & Size Stability`, `Config Validation`, `Routes & Sequence Check`, `Architecture & One Implementation`, `Items Not Points Glossary`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `ADR 0008: If we ship on Forge, Forge calls a hosted calculator` connect `Foundational ADRs & Forge README` to `Changelog, Manifest & Runbooks`, `Browser Suites & Early Forge History`, `ADR Index & Later ADRs`, `Intake Forecasting`, `Tools Compute Principle`, `Hosted Calculator (Retired)`, `Monte Carlo Forecaster`, `CLAUDE.md Constraints & ADR Index`, `Jira OAuth Login`, `Issue Selection & Slicing`, `Security Suite`, `Sequencing Without Scores`, `Facts Pack Metrics`, `Live Series Server`, `Dashboard Forecast Rendering`, `Calculator Retirement (ADR 0031)`, `Route Migration Tests`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **What connects `ASK_TEXT_FIELDS`, `CALC_FIELDS`, `_epics` to the rest of the system?**
  _283 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Weekly Brief Composition` be split into smaller, more focused modules?**
  _Cohesion score 0.061815336463223784 - nodes in this community are weakly interconnected._