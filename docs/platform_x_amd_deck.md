# Chip Orchestra × AMD 

### An AI-native EDA orchestration platform, built to run fully on AMD

**Partnership deck**
Prepared for: Efison Lisan Teknologi (efisonlt.com)
Prepared by: Radhian Ferel Armansyah

---

## TL;DR

- **What Chip Orchestra is:** an AI-native platform that turns a natural-language spec into
  verified RTL and a manufacturable GDSII, running the *entire* RTL-to-GDSII lifecycle as one
  observable, human-gated execution graph, not a pile of disconnected scripts.
- **Why now:** LLMs made "generate Verilog" easy; nobody made "orchestrate the whole chip flow"
  trustworthy. The gap is orchestration + observability + open compute, exactly our lane.
- **The AMD thesis:** the whole stack, the LLM (self-hosted GLM-5.2 on ROCm) *and* the EDA
  back end (OpenLane/OpenROAD, which is CPU/EPYC-bound), runs on AMD silicon. No CUDA, no
  proprietary-API lock-in.
- **The Efison thesis:** Efison already operates AMD-powered HPC (ALELEON, EPYC + accelerators)
  and sells "Computation for Everybody." Chip Orchestra is a high-value, sticky, sovereign
  workload that monetizes that exact fleet.
- **The ask:** co-validate Chip Orchestra on Efison's AMD hardware, publish a joint reference
  design + benchmark, and stand up "Chip design as a service, on Indonesian AMD infrastructure."

---

## Why we built Chip Orchestra

Modern digital chip development is still stitched together from disconnected tools, tribal Tcl
scripts, and manual hand-offs. AI improved *RTL generation*, but there is still no unified
execution layer that owns the **complete** design lifecycle with observability and human control.

We deliberately reframed the question:

```mermaid
flowchart LR
    Q1["❓ Can AI generate Verilog?<br/>(solved-ish, commoditized)"]
    Q2["✅ Can AI orchestrate<br/>RTL-to-GDSII journey while<br/>engineers still in control?"]
    Q1 -->|"the wrong question"| Q2
    style Q1 fill:#f4d7d7,stroke:#c0392b
    style Q2 fill:#d5f0dd,stroke:#1e8449
```

The status quo vs. what we orchestrate:

```mermaid
flowchart TB
    subgraph OLD["Today: fragmented, opaque, un-reproducible"]
        direction LR
        A1["Spec in a doc"] --> A2["Hand-written RTL"]
        A2 --> A3["Sim scripts"]
        A3 --> A4["Vendor synth GUI"]
        A4 --> A5["PnR / signoff silo"]
        A5 --> A6["Email + tribal knowledge"]
    end
    subgraph NEW["Chip Orchestra: one observable execution graph"]
        direction LR
        B0["Natural-language spec"] --> B1["AI Plan"]
        B1 --> B2["RTL + Testbench gen"]
        B2 --> B3["Sim / Lint + self-repair"]
        B3 --> B4["Synth → PnR → DRC/LVS"]
        B4 --> B5["GDS → Signoff → Export"]
        B5 --> B6["Every artifact, prompt & retry traced"]
    end
    OLD -.->|"we replace this"| NEW
```

**Core design principles that make it defensible:**

- **Task-first orchestration**, every design is a structured task owning its inputs, DAG,
  artifacts, reports, approvals and outputs.
- **Transparent AI**, every prompt, retrieved context, patch, retry and reasoning step stays
  visible. No black box.
- **Unified EDA execution**, sim, lint, synth, PnR, GDS, signoff run in one pipeline with full
  artifact lineage.
- **Human-in-the-loop**, RTL edits, implementation and tapeout stay gated behind explicit human
  approval.

---

## The system today (what already works)

An 11-stage orchestrated pipeline across four planes and six containers.

```mermaid
flowchart TB
    subgraph EXP["Experience Plane"]
        SPA["Frontend SPA<br/>React + Vite"]
    end
    subgraph OP["Orchestrator Plane"]
        OPS["Orchestrator Service<br/>Go + Gin + GORM"]
        DAG["DAG Scheduler<br/>11-stage state machine"]
    end
    subgraph EXEC["Execution Plane"]
        AG["Agent Service<br/>FastAPI + LangGraph"]
        EDA["EDA Service<br/>OpenLane / LibreLane / OpenROAD"]
    end
    subgraph DATA["Data Plane"]
        MYSQL[("MySQL")]
        REDIS[("Redis cache + pub/sub")]
    end
    LLM["Self-hosted GLM-5.2<br/>on AMD ROCm (vLLM / ATOM)"]

    SPA --> OPS --> DAG
    DAG --> AG
    DAG --> EDA
    AG --> LLM
    OPS --> MYSQL
    OPS --> REDIS
    AG --> REDIS
    EDA --> MYSQL
    style LLM fill:#ffe6cc,stroke:#d35400
    style EDA fill:#e8f0fe,stroke:#1a73e8
```

The 11 stages, every one observable (AI reasoning, logs, artifacts, retries, reports, approval
checkpoints):

`SPEC_INGEST → PLAN → RTL_GEN → TB_GEN → SIM → LINT → SYNTH → PNR → DRC_LVS → SIGNOFF → EXPORT`

The **ROCm self-hosting path already exists** in this very folder
(`deploy/selfhosted-llm-rocm/`): it points `agent-service` at an OpenAI-compatible vLLM-ROCm /
ATOM server with **zero application code changes**, only env vars and a serving container.

---

## Why AMD, and why "fully AMD" is a genuine differentiator

Chip Orchestra has **two compute-hungry halves**, and both map cleanly onto AMD silicon:

```mermaid
flowchart LR
    subgraph GPU["GPU half, the reasoning engine"]
        direction TB
        G1["LLM planning, RTL/TB gen,<br/>verification, self-repair"]
        G2["Self-hosted GLM-5.2<br/>on AMD Instinct + ROCm"]
        G1 --> G2
    end
    subgraph CPU["CPU half, the EDA back end"]
        direction TB
        C1["Synthesis, PnR, DRC/LVS,<br/>GDS, signoff (OpenROAD/OpenLane)"]
        C2["Massively parallel,<br/>runs great on AMD EPYC cores"]
        C1 --> C2
    end
    GPU -->|"one platform,<br/>one vendor"| CPU
    style G2 fill:#ffe6cc,stroke:#d35400
    style C2 fill:#e8f0fe,stroke:#1a73e8
```

Most "AI for chips" stories are GPU-only and quietly assume NVIDIA + CUDA. Ours is different:

- **The LLM runs on AMD Instinct via ROCm**, ROCm is the industry's only *open* GPU software
  platform, which frees customers from single-vendor lock-in [1]. The MI300X packs 192 GB HBM3
  at 5.3 TB/s [2]; MI325X extends HBM to 256 GB; MI355X (CDNA4) reaches 288 GB, ~8 TB/s and
  native FP4 [3].
- **The EDA back end is CPU-bound** and thrives on EPYC core counts, so an all-AMD node keeps
  *both* halves on the same fleet, same procurement, same support contract.
- **Model quality is identical to cloud** (same open GLM-5.2 weights); only throughput/latency
  depends on tuning (FP8/MXFP4, MTP speculative decoding, AITER kernels, correct DSA backend).

Hardware profiles already shipped in this folder:

| `HW_PROFILE` | GPUs | HBM/GPU | Quant | Note |
|---|---|---|---|---|
| `mi300x` | 8× MI300X | 192 GB | FP8 | Mainstream, validated, start here |
| `mi325x` | 8× MI325X | 256 GB | FP8 | More KV/concurrency headroom |
| `mi355x-fp8` | 4× MI355X | 288 GB | FP8 | CDNA4, ~8 TB/s |
| `mi355x-fp4` | 4× MI355X | 288 GB | MXFP4 | Native FP4, **best perf/TCO** |

---

## Why Efison, the mutual benefit

Efison Lisan Teknologi ("Computation for Everybody") already operates **AMD-powered HPC** in
Indonesia: the ALELEON Supercomputer is built on **AMD EPYC** CPUs with accelerators and 100 Gbps
Mellanox interconnect, and offers public HPC plus system integration [4][5]. Chip Orchestra is a
near-perfect workload for that fleet.

```mermaid
flowchart TB
    subgraph CO["Chip Orchestra brings"]
        X1["A sticky, high-value vertical<br/>workload (chip design)"]
        X2["Uses BOTH EPYC (EDA) and<br/>Instinct (LLM), fills the fleet"]
        X3["Sovereign / on-prem story:<br/>IP never leaves Indonesia"]
    end
    subgraph EF["Efison brings"]
        Y1["Existing AMD HPC capacity<br/>+ ops expertise"]
        Y2["Local market, billing,<br/>SI & support channel"]
        Y3["Credibility: 'first AMD HPC<br/>in Indonesia'"]
    end
    subgraph WIN["Joint outcome"]
        Z1["'Chip design as a service'<br/>on Indonesian AMD infra"]
        Z2["Reference design + benchmark<br/>co-marketed with AMD"]
        Z3["New revenue line for Efison,<br/>go-to-market for us"]
    end
    X1 --> Z1
    X2 --> Z1
    Y1 --> Z1
    Y2 --> Z3
    X3 --> Z1
    Y3 --> Z2
    Z1 --> Z2 --> Z3
    style WIN fill:#d5f0dd,stroke:#1e8449
```

**Why it's compelling for Efison specifically:**

- **Higher-margin utilization** of AMD capacity than generic HPC batch jobs, chip design is
  premium, recurring, and latency-sensitive (keeps GPUs warm).
- **Sovereign compute angle**, semiconductor IP is sensitive; "your design never leaves
  Indonesian soil, on open AMD infrastructure" is a real selling point vs. US SaaS EDA.
- **AMD co-marketing**, a published all-AMD RTL-to-GDSII reference is exactly the kind of
  ecosystem win AMD amplifies, giving Efison visibility beyond Indonesia.
- **Zero lock-in for Efison's customers**, ROCm + open-source EDA (OpenLane/OpenROAD) means no
  per-seat proprietary EDA license floor to resell.

---

## Market position, where the money and the moats are

The EDA market is a tight oligopoly: TrendForce data for 2024 puts **Synopsys ~31%, Cadence ~30%,
Siemens EDA ~13%, ~74% combined** [6], and the big three's combined share has climbed from under
75% (2014) to over 85% (2023) by other counts [7]. Synopsys closed a **$35B Ansys acquisition** in
July 2025, consolidating further [8]. Meanwhile a new wave of **AI chip agents** (e.g. ChipAgents,
which raised a $21M Series A backed by Micron/MediaTek/Ericsson, claiming up to 10x productivity)
is attacking the *design-authoring* layer [9][10].

Two structural gaps neither camp fills well:

1. Incumbents own signoff-grade tools but are **closed, expensive, GPU/CUDA-agnostic-at-best**, and
   not orchestration-native.
2. New chip agents are **IDE plugins for RTL/verification**, they make an engineer faster inside
   the old flow, but they don't own the *end-to-end orchestrated pipeline* or the *compute layer*.

```mermaid
quadrantChart
    title Positioning, orchestration depth vs. openness of stack
    x-axis "Closed / proprietary stack" --> "Open / self-hostable stack"
    y-axis "Point tool / plugin" --> "Full RTL-to-GDSII orchestration"
    quadrant-1 "Open + orchestrated (our lane)"
    quadrant-2 "Closed but orchestrated"
    quadrant-3 "Closed point tools"
    quadrant-4 "Open point tools"
    "Synopsys / Cadence / Siemens": [0.18, 0.72]
    "ChipAgents / chip agents": [0.30, 0.30]
    "Copilot-style RTL assistants": [0.42, 0.20]
    "OpenLane / OpenROAD (raw)": [0.82, 0.45]
    "Chip Orchestra + AMD": [0.85, 0.88]
```

---

## How we differentiate (feature-level)

| Dimension | Incumbent EDA (Synopsys/Cadence/Siemens) | AI chip agents (ChipAgents et al.) | Raw open EDA (OpenLane) | **Chip Orchestra + AMD** |
|---|---|---|---|---|
| Scope | Full flow, best-in-class signoff | RTL/verification authoring | Full flow, batch/no-UI | **Full flow, AI-orchestrated + observable** |
| AI orchestration | Bolt-on GenAI features | Agent inside editor | None | **Native, multi-agent, 11-stage DAG** |
| Observability | Log files, closed | Editor-scoped | Terminal logs | **Every prompt/retry/artifact traced in browser** |
| Human-in-the-loop | Manual, tool-by-tool | Suggestion accept/reject | N/A | **Explicit approval gates on RTL/impl/tapeout** |
| Compute stack | Proprietary, mostly NVIDIA/x86 | Cloud API (NVIDIA) | CPU tools | **Fully AMD: ROCm LLM + EPYC EDA** |
| Lock-in | High (licenses + APIs) | High (SaaS API) | Low | **Low, open weights + open EDA + open ROCm** |
| Deploy | On-prem/cloud, heavy | SaaS | Self-host | **Self-host, sovereign, container-native** |

**Our wedge in one sentence:** *the only AI-native, fully observable RTL-to-GDSII orchestrator that
runs end-to-end on open, self-hostable, all-AMD infrastructure.* Incumbents won't abandon their
CUDA/proprietary margins; agent startups won't build the compute layer or the signoff pipeline.

---

## Product & development roadmap

```mermaid
gantt
    title Chip Orchestra × AMD × Efison, phased roadmap
    dateFormat YYYY-MM-DD
    axisFormat %b '%y

    section Phase 0, Foundation (done)
    ROCm self-host path (vLLM/ATOM)      :done, p0a, 2026-05-01, 2026-07-01
    11-stage orchestration + OpenLane     :done, p0b, 2026-04-01, 2026-07-01

    section Phase 1, Validate on Efison (0-3 mo)
    Deploy on ALELEON (MI300X + EPYC)     :active, p1a, 2026-08-01, 45d
    Joint reference design + benchmark    :p1b, after p1a, 30d
    Perf tuning (FP8/MXFP4, AITER, MTP)   :p1c, after p1a, 40d

    section Phase 2, Productize service (3-6 mo)
    Multi-tenant + quota/billing hooks    :p2a, 2026-11-01, 60d
    Sovereign / on-prem hardening         :p2b, 2026-11-15, 45d
    MXFP4 on MI355X TCO track             :p2c, 2026-12-01, 45d

    section Phase 3, Scale & moat (6-12 mo)
    Distributed EDA across EPYC nodes     :p3a, 2027-02-01, 75d
    Design-knowledge RAG + repo-aware     :p3b, 2027-03-01, 75d
    Analog/MS + FPGA flow extensions      :p3c, 2027-04-01, 90d
```

---

## Opportunity map, benefit vs. cost vs. risk

```mermaid
quadrantChart
    title Prioritization, pick high-benefit / low-cost first
    x-axis "Low cost / effort" --> "High cost / effort"
    y-axis "Low benefit" --> "High benefit"
    quadrant-1 "Do next (invest)"
    quadrant-2 "Quick wins, do FIRST"
    quadrant-3 "Fill-ins (later)"
    quadrant-4 "Question / defer"
    "Deploy on Efison AMD (reuse ROCm path)": [0.22, 0.90]
    "Joint benchmark + reference design": [0.28, 0.82]
    "MXFP4 perf/TCO preset (MI355X)": [0.30, 0.72]
    "Sovereign on-prem packaging": [0.40, 0.78]
    "Multi-tenant billing/quota": [0.60, 0.68]
    "Distributed EDA across EPYC": [0.72, 0.66]
    "Analog/mixed-signal + FPGA": [0.85, 0.55]
    "Custom signoff to match Calibre": [0.90, 0.40]
```

Detailed table (H = high, M = medium, L = low):

| Opportunity | Benefit | Cost/effort | Risk | Verdict |
|---|---|---|---|---|
| **Deploy on Efison AMD reusing the existing ROCm path** | H | **L** | L | ⭐ Do first |
| **Joint reference design + published benchmark (co-market w/ AMD)** | H | **L** | L | ⭐ Do first |
| **MXFP4 perf/TCO preset on MI355X** | H | L–M | M (CDNA4 accuracy caveat) | ⭐ Do first |
| Sovereign/on-prem packaging (IP-stays-local) | H | M | L | Do next |
| Multi-tenant + quota/billing for "design-as-a-service" | H | M–H | M | Do next |
| Distributed EDA across EPYC nodes (parallel PnR) | M–H | H | M | Phase 3 |
| Design-knowledge RAG / repo-aware assistant | M | M | M | Phase 3 |
| Analog/mixed-signal + FPGA flows | M | H | H | Later |
| Custom signoff to rival Calibre-clean | H (long term) | **H** | **H** | Defer / partner |

**High-benefit, low-cost wins (start here):**

1. **Stand it up on Efison's AMD box using the ROCm path we already shipped**, near-zero net-new
   engineering; env vars + serving container only.
2. **Publish a joint all-AMD RTL-to-GDSII reference + benchmark**, cheap to produce, high
   marketing leverage, and the single most credible proof point for the partnership.
3. **Ship the MXFP4/MI355X preset**, best perf/TCO with tuning we already understand; strong
   "cheaper than the NVIDIA+proprietary alternative" narrative.

---

## Challenges & tradeoffs

We are not pretending this is free. Key tradeoffs we've consciously made:

```mermaid
mindmap
  root((Challenges<br/>& tradeoffs))
    Signoff credibility
      Open EDA is not yet Calibre-grade
      Foundries specify Calibre-clean DRC/LVS
      Tradeoff: target education/SkyWater/GF first, partner for advanced-node signoff
    ROCm maturity
      Smaller ecosystem than CUDA
      MI355X FP8 GEMM accuracy caveat on older images
      Tradeoff: pin validated images, spot-check reasoning, ride ROCm's fast improvement curve
    Model ops burden
      ~750GB FP8 weights, big first boot
      Empty API key = silent mock output
      Tradeoff: shipped preflight/healthcheck scripts + HW profiles to de-risk ops
    Market trust
      Incumbents own habits and sign-off trust
      Tradeoff: win on openness + observability + sovereignty, not on beating Calibre day one
    Business model
      Open stack = no license moat
      Tradeoff: moat is orchestration + data/traces + AMD-optimized ops, not IP lockup
```

Explicit tradeoff decisions worth calling out:

- **We chose openness over a license moat.** Open weights + open EDA + ROCm means low lock-in for
  customers (a selling point) but no software-license annuity, so our moat must be the
  orchestration layer, observability/traces, and AMD-tuned operations, not lock-in.
- **We chose self-hosting over easy SaaS.** Sovereignty and cost control win in target markets, at
  the price of heavier ops (large model weights, ROCm tuning), mitigated by the preflight /
  healthcheck / profile scripts already in this folder.
- **We chose to *not* fight Calibre on day one.** Advanced-node signoff trust is the incumbents'
  fortress; we start where open PDKs (SkyWater SKY130, GF180) and education/prototyping demand is
  real, and treat advanced-node signoff as a partner/later problem.
- **We chose GLM-5.2 open weights over a frontier closed API.** Quality is competitive and
  self-hostable on AMD; we accept being one step behind the absolute frontier in exchange for
  control, cost, and the all-AMD story.

---

## The ask & next steps

```mermaid
sequenceDiagram
    participant CO as Chip Orchestra
    participant EF as Efison
    participant AMD as AMD (ecosystem)
    CO->>EF: Provide container stack + ROCm serving path
    EF->>CO: Provision AMD node (MI300X + EPYC) on ALELEON
    CO->>EF: Deploy + tune (FP8/MXFP4, AITER, MTP)
    CO->>AMD: Share all-AMD RTL-to-GDSII reference + benchmark
    AMD-->>EF: Co-marketing amplification
    EF->>CO: Launch "chip design as a service" (local, sovereign)
    Note over CO,EF: New revenue line for Efison,<br/>go-to-market + proof point for us
```

**Concrete asks for a pilot (all low-cost, high-signal):**

1. One AMD node (ideally 8× MI300X + EPYC head node) for a 6–8 week validation.
2. Co-author a public reference design + benchmark on Efison AMD infrastructure.
3. Explore a joint "Chip Design as a Service" offering with Efison as the local/sovereign channel.

**What we bring on day one:** a working, container-native platform whose ROCm self-hosting path
(this exact folder) needs *only env vars and a serving container*, no application code changes.

---

## References

1. AMD, *Accelerating AI and HPC with AMD Instinct MI300X* (ROCm as the industry's only open GPU software platform): https://www.amd.com/en/partner/articles/instinct-mi300x-accelerating-ai-hpc.html
2. AMD, *Instinct MI300X Accelerators* (192 GB HBM3, 5.3 TB/s, 304 CUs): https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html
3. AMD ROCm docs, *MI300 Series / MI350 Series microarchitecture* (CDNA, FP8/FP4, memory): https://rocm.docs.amd.com/en/latest/reference/gpu-arch/mi300.html
4. Efison Lisan Teknologi, company homepage (ALELEON, AMD EPYC + accelerators + Mellanox, public HPC): https://efisonlt.com/
5. Efison, *Spesifikasi ALELEON Supercomputer* (ALELEON Mk.V specs): https://wiki.efisonlt.com/wiki/Spesifikasi_ALELEON_Supercomputer
6. TrendForce via press (2024 EDA share: Synopsys ~31%, Cadence ~30%, Siemens ~13%, ~74% combined): https://finance.sina.com.cn/jjxw/2025-07-04/doc-infehuet9617966.shtml
7. Embedded.com, *Taking Stock of the EDA Industry* (top-3 combined share >85% by 2023, Griffin Securities/DAC 2024): https://www.embedded.com/taking-stock-of-the-eda-industry/
8. Mordor Intelligence, EDA tools market (Synopsys' $35B Ansys acquisition, July 2025): https://www.mordorintelligence.com/industry-reports/electronic-design-automation-eda-tools-market
9. ChipAgents, *Oversubscribed $21M Series A* (Bessemer; Micron, MediaTek, Ericsson): https://www.businesswire.com/news/home/20251021677325/en/
10. ChipAgents, product site (agentic AI chip design/verification, "10x faster"): https://chipagents.ai/
11. OpenROAD Project, open-source RTL-to-GDSII physical design (SkyWater SKY130, GF180): https://en.wikipedia.org/wiki/OpenROAD_Project
12. vLLM GLM-5.2 recipe (ROCm serving reference): https://recipes.vllm.ai/zai-org/GLM-5.2

> Market-share and funding figures are drawn from the sources above; specific quantitative claims
> (EDA shares, funding amounts) should be re-verified against the primary source before external use.
