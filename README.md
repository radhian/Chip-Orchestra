# Chip Orchestra: End\-to\-end AI\-Native Digital Chip Design Platform 

## Background

**North star:** turn Chipster from a collection of AI\-assisted design tools into a **task\-centric digital IC and SoC Platform** where RTL generation, verification, synthesis, and tapeout preparation are orchestrated as observable browser\-native workflows\.

**Chipster** already demonstrates the right technical direction: AI\-assisted Verilog generation, automated verification loops, OpenLane integration, and standard\-cell generation\. Based on the current public project baseline, the next product step should not be just “more models”. This should be a **unified execution surface** that makes complex hardware flows feel as manageable as modern AI generation tasks\.

The product proposal below reframes **Chipster** onto **Chip Orchestra**, such have four experience pillars:

1. **Task\-first orchestration** so users launch and track digital design work as structured jobs rather than ad hoc scripts\.

2. **Inspectable agent collaboration** so every AI decision, patch, and retry remains reviewable by engineers\.

3. **Integrated EDA execution** so simulation, lint, synthesis, PnR, and signoff share one lineage of artifacts and metrics\.

4. **Tapeout\-oriented delivery** so the end state is not just “generated RTL”, but a clean handoff package with reports, waivers, and approvals\.

To ground the proposal in the current Chip Orchestra baseline, the recommendations below focus on rebranding the platform into a more explicit AI\-native digital IC and SoC execution system\.

---

## Product framing

### What we are building

**Chip Orchestra Digital** is a browser\-based platform for digital IC and SoC development that combines:

- AI agent planning

- Web\-based RTL authoring and review

- Managed verification and synthesis pipelines

- Task dashboards with artifacts, logs, and stage\-level visibility

- Production\-minded signoff and export workflows

### Why this is the right continuation ofChip Orchestra

The currentChip Orchestra documentation already describes a flow from natural language prompt to Verilog, testbench generation, simulation, synthesis, and GDS output\. The missing layer is the **product operating model** around that flow:

- how tasks are created

- how runs are observed

- how errors are triaged

- how multiple artifacts are compared

- how engineers intervene safely

- how final deliverables are packaged

That operating model is what this proposal provides\.

### CurrentChip Orchestra strength

- Strong AI\-assisted generation story

- Demonstrated verification loop

- OpenLane/OpenROAD foundation

- Good innovation narrative from Chipathon and taped\-out success

- Self hosted LLM model 

### Current product gap

- Workflow feels tool\-centric instead of task\-centric

- Limited run visibility for non\-authors

- No unified control plane for retries, approvals, and artifact lineage

- Browser experience is not yet the primary product surface

- Dependency to 3rd party API for LLM 

---

## Proposed design principles

### 1\. Design around tasks, not tools

The platform homepage should look like an execution console rather than a landing page\. The primary object is a **design task**, for example:

- "Generate FFT RTL from spec"

- "Rescue failing simulation for AES block"

- "Run synthesis closure for UART controller"

- "Produce signoff bundle for RISC\-V peripheral"

Each task owns: scope, inputs, stage graph, artifacts, logs, metrics, approvals\. final outputs

### 2\. Treat AI as a visible collaborator

AI should not behave like a black box\. For each stage, the UI should expose:

- what prompt or context the agent used

- what sources or prior designs were retrieved

- what patch or file was generated

- what EDA command or runner executed next

- why a retry or alternative was chosen

### 3\. Keep human review in the loop at risk boundaries

Autonomy is valuable during exploration, but hardware flows need gated review at important moments:

- before patching critical RTL

- before advancing from verification to synthesis

- before packaging signoff artifacts

- before applying waivers

### 4\. Make failure diagnosis first\-class

In chip design, value often comes from explaining **why** a run failed\. The product should therefore optimize for:

- clustered errors, not raw logs only

- stage\-level summaries

- waveform and assertion shortcuts

- diff\-aware patch previews

- recommended next actions with confidence and tradeoff summaries

---

## Scope for V1

**V1 recommendation:** focus on **digital IC and SoC automation only**, while preserving future extension points for analog, photonics, and standard\-cell generation\.

### In scope

- Repository\-aware task dashboard

- Create\-task workflow for digital design jobs

- Browser\-based RTL and testbench workspace

- AI\-assisted RTL and testbench generation

- Integrated simulation, lint, and coverage loops

- Managed synthesis and implementation flow with OpenLane/OpenROAD

- Artifact center for reports, waveforms, netlists, and patches

- Signoff package generation with approvals and waivers

### Out of scope for V1

- Other chip desigh workbech \(analog design, RF/Microwave circuit, photonic\)

- Deep custom layout editing inside the browser

- Broad marketplace or ecosystem monetization features

- Multi\-tenant enterprise policy engine beyond basic Role\-Based Access Control \(RBAC\)

---

## Information architecture

|Primary surface|Purpose|Key interactions|
|---|---|---|
|Overview Console|Queue of active and historical design tasks|Filter by repo, owner, stage, failure mode, approval state, and run outcome|
|Create Design Task|Structured launch flow for new AI or EDA work|Choose task type, connect to a repository \(existing or template\-generated\), select PDK, set autonomy level, launch managed run|
|Task Detail and Runbook|Single pane of glass for one task lifecycle, including task\-scoped sub\-tabs for execution, RTL editing, and signoff|Runbook timeline, logs, artifacts, reruns, AI explanations, approvals, issue clustering, RTL patch review, and signoff packaging|

---

## Core workflows

### Workflow A: Prompt/spec to working RTL

1. Engineer creates a **Generate RTL** task\.

2. Platform parses the natural language brief and repository\-backed design context\.

3. Retrieval layer pulls prior modules, interface templates, and relevant design examples\.

4. AI agents propose RTL, testbench, and assertions\.

5. Simulation and lint run automatically\.

6. Failures loop back into agent repair with visible traceability\.

7. Passing revisions become versioned artifacts in the task detail page\.

### Workflow B: Verification rescue

1. Engineer creates a **Fix failing verification** task from an existing branch or run\.

2. Platform ingests failing test logs, assertion outputs, waveform clips, and recent diffs\.

3. AI clusters likely root causes and proposes patches\.

4. Engineer reviews patch rationale and accepts or rejects changes\.

5. Regression reruns and coverage deltas are attached to the same task object\.

### Workflow C: RTL\-to\-GDS execution

1. Engineer promotes a verified revision into an **Implementation** stage\.

2. Synthesis, floorplanning, placement, routing, STA, DRC, and LVS run in managed lanes\.

3. Core implementation reports are normalized into a compact, task\-level summary for MVP review\.

4. The task exposes only the most important blockers and recommendations needed to move the RTL\-to\-GDS flow forward\.

5. Clean runs advance to delivery packaging\.

### Workflow D: Signoff handoff

1. Platform gathers GDS, netlist, liberty views, constraints, reports, waivers, and task narrative\.

2. Required approvers review the package\.

3. Once approved, the bundle is exported as a formal handoff artifact\.

---

## UX pattern adapted from task\-based AI generation consoles

The target experience should reuse the strongest interaction patterns from modern managed generation products, but adapt them for hardware:

|Pattern|Why it works|Chip Orchestra adaptation|
|---|---|---|
|Task list with strong filters|Lets users scan many runs quickly and find blockers fast|Filter by repo, module, stage, toolchain, PDK, owner, and status|
|Task detail page with timeline|Turns long\-running work into understandable steps|Show spec → RTL → TB → sim → lint → synth → PnR → signoff as linked stages|
|Inline logs and artifacts|Reduces context switching across tools|Expose waveform, reports, diffs, patches, and metrics from the same detail view|
|Visible retries and reruns|Builds trust in automation|Every retry should be attributable to a human or AI reason with before/after diffs|
|Opinionated create\-task flow|Makes advanced systems usable for more people|Wizard for task type, PDK, review gates, constraints, and runtime policy|

---

## Success metrics

|Metric|Target direction|Why it matters|
|---|---|---|
|Time from spec to first passing RTL revision|Down|Measures whether AI \+ orchestration reduce front\-end iteration time|
|Manual steps per successful design task|Down|Shows whether browser\-native workflow actually removes tool friction|
|Verification rescue turnaround time|Down|Captures diagnostic value, not just generation value|
|Stage observability score|Up|Teams trust systems that expose what happened and why|
|Signoff\-ready export rate|Up|Measures progress toward production usefulness rather than demo novelty|

---

## Main risks and mitigation

- **Risk: AI\-generated RTL is treated as authoritative too early**
Mitigation: require review gates for risky modules and preserve diff\-based explainability\.

- **Risk: EDA environments become brittle across tasks**
Mitigation: normalize execution into managed lanes with reproducible environment metadata\.

- **Risk: UI becomes too generic and loses hardware depth**
Mitigation: make waveform, coverage, timing, netlist, and report viewers first\-class, not secondary links\.

- **Risk: product complexity overwhelms new users**
Mitigation: use opinionated presets, task templates, and recommended default pipelines\.

---

## Recommended V1 screen set

The embedded wireframe below covers the proposed primary screens and the task\-scoped sub\-sections inside Task Detail and Runbook:

- Overview Console

- Create Design Task

- Task Detail and Runbook

- Runbook tab

- RTL Workspace tab

- Signoff and Delivery tab

## Wireframe walkthrough \(MVP UI\)

### Overview Console

![Image](https://internal-api-drive-stream.larkoffice.com/space/api/box/stream/download/authcode/?code=ZmEwNDA2YzY1NmE0M2UyNWRlZWRiZGUwYWI2ZjExZDNfMWE2YjY1YTA0YTBmOTQyYzFjMDA0OGNhYzE0NmI0NjlfSUQ6NzY0NjMxMTU2NjEyODMxOTQ0N18xNzgwMjk4MTMyOjE3ODAzODQ1MzJfVjM)

|Element|Purpose|Content and actions|
|---|---|---|
|Sidebar navigation|Switch between high\-level surfaces|Three buttons: **Overview Console**, **Create Design Task**, and **Task Detail and; Runbook**\. Clicking a button swaps the main content area to the corresponding screen\.|
|Filter chips|Quickly scope the task list|Four chips: **All repos**, **My tasks**, **Needs review**, and **Failed**\. In MVP these act as simple filters over the task list\.|
|Task table|Primary entry point into task\-centric flows|Columns: **Task**, **Owner**, **Current stage**, **ETA**, **Status**\. Rows include examples like FFT Accelerator 1024p, AES\-128 Core Refresh, UART Controller Lite, and RISC\-V GPIO Bridge\. Clicking a row selects that task and opens **Task Detail and Runbook** for that design\.|
|RTL\-to\-GDS workflow strip|Explain the MVP stage model|Five informational cards: **Ingest spec**, **Agent plan**, **Verify loop**, **Implement**, and **Deliver**\. These explain the stage flow and are descriptive rather than interactive in MVP\.|

### Create Design Task

![Image](https://internal-api-drive-stream.larkoffice.com/space/api/box/stream/download/authcode/?code=ZWVkM2QyNTBhNmQ5NmU1N2U3OWRlMWE5YjY2MWY1ZTFfNTkyMzIyMDZjYjZhNzc4NDNjNWViODkyNmZhODJjMWFfSUQ6NzY0NjMxMTYzNDA1MDIwNjkyMV8xNzgwMjk4MTMyOjE3ODAzODQ1MzJfVjM)

|Element|Purpose|Content and actions|
|---|---|---|
|Header and badge|Set context for task launch|Title: **Create design task**\. Subtitle explains the lean RTL\-to\-GDS MVP launch flow\. Badge: **MVP launch**\.|
|Step rail|Guide users through launch decisions|Four textual steps: **Choose scope**, **Connect source**, **Pick environment**, and **Set agent policy**\. In MVP these steps are descriptive labels above the form\.|
|Form fields|Capture the minimal task configuration|Key fields: **Task name**, **Launch mode**, **Design brief**, **Repository source**, **Bootstrap option**, **PDK / library**, and **Review gate**\. The important change is that the source is repo\-oriented: users either link an existing repository or generate a new one from the `digital\-block\-starter` template\.|

### Task Detail and Runbook – header and shared elements

|Element|Purpose|Content and actions|
|---|---|---|
|Task header|Summarize the selected task|Shows the selected task name, summary, and status\-style pills such as **Running**, **Attempt \#4**, and **Manual review before signoff**\. The header persists across all task\-scoped tabs\.|
|Phase timeline|Expose stage\-by\-stage progress|Eight nodes: **Spec**, **RTL**, **TB**, **Sim**, **Lint**, **Synth**, **PnR**, and **Signoff**\. Each node has a short note and a simple state such as Done, Active, or Queued\.|
|Task tabs|Scope views per task|Three tabs: **Runbook**, **RTL Workspace**, and **Signoff and Delivery**\. Clicking a tab swaps the content inside the Task Detail screen while keeping the same task context\.|

### Runbook tab

![Image](https://internal-api-drive-stream.larkoffice.com/space/api/box/stream/download/authcode/?code=ZDRjYTAxYzQ2MWU1ZmFkNDAzMzZhNWUzZjU3Yzk5YzVfZWFkOTAxZDE5ODg3MmYxZGZjNDM5MjA0NTgyOGVjY2JfSUQ6NzY0NjMxMTgxNzUwNTkxNzkyNl8xNzgwMjk4MTMyOjE3ODAzODQ1MzJfVjM)

|Element|Purpose|Content and actions|
|---|---|---|
|Execution log|Show recent actions in the flow|Example items include **OpenLane synthesis launched**, **Critical path cluster isolated**, and **Alternative pipeline proposal generated**\. In MVP this is a readable activity feed\.|
|Artifacts and reports|Surface key outputs per stage|Example artifacts include **synth\_****report\.rpt**, **fft\_****core\_****rev4\.sv**, and **agent\_****trace\.json**\. Conceptually, clicking one would open it in an appropriate viewer\.|
|AI diagnosis|Summarize suggested next actions|Examples include timing, power, and review suggestions\. These are guidance summaries rather than auto\-fix controls in MVP\.|

### RTL Workspace tab

![Image](https://internal-api-drive-stream.larkoffice.com/space/api/box/stream/download/authcode/?code=ZGNjMTYyYjRlOWFjYjNlMjI1MGMyNmNhN2I1OTRiMzRfMmE4OGQ2OWMzYmNkMmJmYTU3MDc2N2QxNmRiMGY5YzlfSUQ6NzY0NjMxMTkyNjcyMjE1MzY4NF8xNzgwMjk4MTMyOjE3ODAzODQ1MzJfVjM)

|Element|Purpose|Content and actions|
|---|---|---|
|RTL editor header<br>|Clarify task scoping|Title: **RTL workspace for ****\&lt;task\-name\&gt;**\. Subtitle explains that the editor belongs to the current task only\. Pills: **RTL draft** and **Diff aware**\.|
|Editor tabs and code area|Show core design files|Tabs: `fft\_core\.sv`, `fft\_core\_tb\.sv`, and `constraints\.sdc`\. The code area shows a representative RTL snippet and the next suggested engineering action\.|
|Verification status summary|Expose pass/fail signals close to the code|Three compact summaries: **Simulation pass set**, **Functional coverage**, and **Lint cleanliness**\. In MVP these are read\-only progress indicators\.|

### Signoff and Delivery tab

![Image](https://internal-api-drive-stream.larkoffice.com/space/api/box/stream/download/authcode/?code=ODliY2VlODRjMjhjYjFlNDNmZDJjMWFjYWE2MjMyZjdfZjE0YzU3OTc2YmMzMDIwZDgxN2RhM2UxNDNjNjY0NTRfSUQ6NzY0NjMxMjA3NjY4MjI1MTQ1NV8xNzgwMjk4MTMyOjE3ODAzODQ1MzJfVjM)

|Element|Purpose|Content and actions|
|---|---|---|
|Signoff header|Scope signoff to the current task|Title: **Signoff and delivery for ****\&lt;task\-name\&gt;**\. Subtitle explains that this is a task\-specific closing view\. Badge: **Tapeout package candidate**\.|
|Checklist items|Track readiness for handoff|Four checklist rows: **Verification baseline frozen**, **Implementation reports normalized**, **Waiver review pending**, and **One\-click handoff bundle**\. These describe the final handoff expectations for MVP\.|

If this direction looks right, the next concrete step should be converting the wireframe into a clickable product spec with component inventory, backend APIs, task schemas, and stage\-specific event contracts\.

