"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AgentDecision,
  AgentId,
  AgentStatuses,
  TeamSituationalState,
  ThoughtEvent,
  TransactionPreview,
  UploadResponse,
  VerdictEvent,
} from "@/types/investigation";
import { formatCurrencyMXN } from "@/lib/utils";

export interface UseAgentSimulationReturn {
  currentCase: UploadResponse | null;
  thoughts: ThoughtEvent[];
  verdict: VerdictEvent | null;
  statuses: AgentStatuses;
  situationalState: TeamSituationalState;
  agentDecisions: Record<AgentId, AgentDecision>;
  isPreparing: boolean;
  isRunning: boolean;
  error: string | null;
  selectedStepId: string | null;
  setSelectedStepId: (id: string | null) => void;
  selectedStep: ThoughtEvent | null;
  startSimulation: (files: File[]) => Promise<void>;
  resetSimulation: () => void;
}

interface ParsedFile {
  name: string;
  headers: string[];
  rows: TransactionPreview[];
  rowCount: number;
}

interface ScheduledStep {
  delayMs: number;
  event: ThoughtEvent;
  agentStatusUpdate?: { agentId: AgentId; status: "reviewing" | "returned" | "complete" };
  agentDecisionUpdate?: { agentId: AgentId; decision: AgentDecision };
  situationalStateUpdate?: Partial<TeamSituationalState>;
}

const waitingStatuses = (): AgentStatuses => ({
  ORCHESTRATOR: "waiting",
  DATA_VALIDATION: "waiting",
  CIRCULAR_FLOWS: "waiting",
  PASSTHROUGH: "waiting",
  RISK_REVIEW: "waiting",
});

const initialSituationalState = (): TeamSituationalState => ({
  stage: "ingestion",
  stageIndex: 0,
  progressPct: 0,
  stageTitle: "Awaiting Dataset Ingestion",
  executiveSummary:
    "The forensic workspace is ready. Once transaction ledgers are uploaded, the team will launch concurrent ingestion, graph cycle detection, and pass-through flow velocity analysis.",
  advances: [
    { label: "Pipeline Status", value: "Ready to simulate" },
    { label: "Target Checks", value: "Closed cycles & bridge accounts" },
    { label: "Voice Narration", value: "ElevenLabs speech enabled" },
  ],
});

const initialAgentDecisions = (): Record<AgentId, AgentDecision> => ({
  ORCHESTRATOR: { task: "Awaiting ledger ingestion", timestamp: new Date().toISOString() },
  DATA_VALIDATION: { task: "Waiting for source files", timestamp: new Date().toISOString() },
  CIRCULAR_FLOWS: { task: "Waiting for normalized inputs", timestamp: new Date().toISOString() },
  PASSTHROUGH: { task: "Waiting for transaction timestamps", timestamp: new Date().toISOString() },
  RISK_REVIEW: { task: "Waiting for pattern correlation", timestamp: new Date().toISOString() },
});

const aliases = {
  origin: ["origin", "nameorig", "from_account", "source", "orig_account", "orig"],
  destination: ["destination", "namedest", "to_account", "target", "dest_account", "dest"],
  amount: ["amount", "value", "monto", "sum"],
  timestamp: ["timestamp", "step", "time", "date", "datetime", "trans_time"],
};

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"' && line[index + 1] === '"' && quoted) {
      value += '"';
      index += 1;
    } else if (character === '"') quoted = !quoted;
    else if (character === "," && !quoted) {
      values.push(value.trim());
      value = "";
    } else value += character;
  }
  values.push(value.trim());
  return values;
}

function columnIndex(headers: string[], candidates: string[]): number {
  return headers.findIndex((header) => candidates.includes(header.toLowerCase().trim()));
}

async function parseFile(file: File): Promise<ParsedFile> {
  const text = await file.text();
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) throw new Error(`${file.name} does not contain any transaction rows.`);
  const headers = splitCsvLine(lines[0]);
  const origin = columnIndex(headers, aliases.origin);
  const destination = columnIndex(headers, aliases.destination);
  const amount = columnIndex(headers, aliases.amount);
  const timestamp = columnIndex(headers, aliases.timestamp);
  if (origin < 0 || destination < 0 || amount < 0) {
    throw new Error(`${file.name} needs origin, destination, and amount columns.`);
  }
  const rows = lines
    .slice(1, 201)
    .map((line, index) => {
      const values = splitCsvLine(line);
      return {
        origin: values[origin] || `UNKNOWN_ORIGIN_${index + 1}`,
        destination: values[destination] || `UNKNOWN_DESTINATION_${index + 1}`,
        amount: Math.max(0, Number(values[amount]) || 0),
        timestamp:
          timestamp >= 0 && Number.isFinite(Number(values[timestamp]))
            ? Number(values[timestamp])
            : null,
      };
    })
    .filter((row) => row.amount > 0);
  if (!rows.length) {
    throw new Error(`${file.name} does not contain valid positive transaction amounts.`);
  }
  return { name: file.name, headers, rows, rowCount: lines.length - 1 };
}

function makeCase(files: ParsedFile[]): UploadResponse {
  const rows = files.flatMap((file) => file.rows);
  const preview = rows.slice(0, 20);
  const accounts = Array.from(new Set(rows.flatMap((row) => [row.origin, row.destination])));
  const volume = rows.reduce((sum, row) => sum + row.amount, 0);
  const edgeRows = preview.slice(0, Math.min(8, preview.length));
  const cycleAccounts = accounts.slice(0, 3);
  const cycles =
    cycleAccounts.length === 3
      ? [
          {
            path: [...cycleAccounts, cycleAccounts[0]],
            length: 3,
            estimated_volume: edgeRows.slice(0, 3).reduce((sum, row) => sum + row.amount, 0),
          },
        ]
      : [];
  const bridge =
    rows.find((row) => rows.some((candidate) => candidate.destination === row.origin))?.origin ||
    accounts[1] ||
    "ACC_BRIDGE_01";
  const bridgeRows = rows.filter((row) => row.origin === bridge || row.destination === bridge);
  const incoming = bridgeRows
    .filter((row) => row.destination === bridge)
    .reduce((sum, row) => sum + row.amount, 0);
  const outgoing = bridgeRows
    .filter((row) => row.origin === bridge)
    .reduce((sum, row) => sum + row.amount, 0);
  const base = Math.max(incoming, outgoing, 1);
  const passthrough = bridge
    ? [
        {
          account: bridge,
          total_in: incoming || base,
          total_out: outgoing || base * 0.94,
          ratio: Math.min(incoming || base, outgoing || base * 0.94) / base,
          time_delta_hours: 18,
        },
      ]
    : [];

  return {
    case_id: `demo-${Date.now().toString(36)}`,
    simulation: true,
    source_files: files.map((file) => file.name),
    filename: files.length === 1 ? files[0].name : `${files.length} CSV files`,
    message: "Frontend workflow simulation prepared.",
    ingestion: {
      total_records: files.reduce((sum, file) => sum + file.rowCount, 0),
      total_volume: Math.round(volume * 100) / 100,
      unique_accounts: accounts.length,
      original_columns: Array.from(new Set(files.flatMap((file) => file.headers))),
      timestamps_synthetic: rows.some((row) => row.timestamp === null),
    },
    preview,
    metrics: {
      total_nodes_analyzed: accounts.length,
      suspicious_nodes_count: Math.min(accounts.length, 4),
      pruned_nodes_count: Math.max(0, accounts.length - 4),
      total_edges_analyzed: rows.length,
      suspicious_edges_count: edgeRows.length,
      pruned_edges_count: Math.max(0, rows.length - edgeRows.length),
      suspicious_volume_mxn:
        Math.round(edgeRows.reduce((sum, row) => sum + row.amount, 0) * 100) / 100,
      detected_cycles_count: cycles.length,
      passthrough_accounts_count: passthrough.length,
      pruning_efficiency_pct: rows.length
        ? Math.round((Math.max(0, rows.length - edgeRows.length) / rows.length) * 10000) / 100
        : 0,
    },
    subgraph: {
      nodes: accounts.slice(0, 6).map((id, index) => ({
        id,
        total_in: 0,
        total_out: 0,
        in_degree: 1,
        out_degree: 1,
        reasons: index < 3 ? ["SIMULATED_PATTERN"] : [],
        risk_score: 0.5,
      })),
      edges: edgeRows.map((row) => ({
        source: row.origin,
        target: row.destination,
        amount: row.amount,
        count: 1,
        timestamps: row.timestamp === null ? [] : [row.timestamp],
        reasons: ["SIMULATED_EVIDENCE"],
      })),
    },
    patterns: { cycles, passthrough_accounts: passthrough },
  };
}

function buildConcurrentSchedule(currentCase: UploadResponse): ScheduledStep[] {
  const fileCount = currentCase.source_files?.length || 1;
  const cycle = currentCase.patterns.cycles[0];
  const passthrough = currentCase.patterns.passthrough_accounts[0];
  const totalRows = currentCase.ingestion?.total_records || 0;
  const totalCols = currentCase.ingestion?.original_columns.length || 4;
  const pruneEfficiency = currentCase.metrics.pruning_efficiency_pct || 88.5;
  const suspVol = currentCase.metrics.suspicious_volume_mxn || 0;
  const passRatioPct = passthrough ? (passthrough.ratio * 100).toFixed(0) : "94";

  let stepCounter = 1;
  const makeId = () => `${currentCase.case_id}:${stepCounter++}`;

  return [
    // --- STAGE 1: INGESTION & SCHEMA NORMALIZATION (T=50ms to T=1200ms) ---
    {
      delayMs: 50,
      event: {
        event_id: makeId(),
        step: 1,
        phase: "Review Scope Initialized",
        headline: "Dataset Ingested",
        metric: `${fileCount} CSV file${fileCount === 1 ? "" : "s"}`,
        message: `${fileCount} CSV file(s) ingested with ${totalRows.toLocaleString("en-US")} total records. Initializing 4 specialist tracks with concurrent schedule.`,
        timestamp: new Date().toISOString(),
        agent_id: "ORCHESTRATOR",
        action: "started",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "ORCHESTRATOR", status: "reviewing" },
      agentDecisionUpdate: {
        agentId: "ORCHESTRATOR",
        decision: {
          task: "Ingesting transaction ledgers",
          decision: `${fileCount} CSV file(s) received`,
          metric: `${totalRows.toLocaleString()} rows`,
          timestamp: new Date().toISOString(),
        },
      },
      situationalStateUpdate: {
        stage: "ingestion",
        stageIndex: 0,
        progressPct: 15,
        stageTitle: "Ingestion & Schema Normalization",
        executiveSummary: `The team has initiated the investigation across ${fileCount} transaction ledger(s). We are verifying field coverage and resolving aliases for origin, destination, amount, and timestamp to establish a clean analytical baseline.`,
        advances: [
          { label: "Records Ingested", value: `${totalRows.toLocaleString()} rows` },
          { label: "Source Files", value: `${fileCount} CSVs` },
          { label: "Phase", value: "Ingestion & schema check" },
        ],
      },
    },
    {
      delayMs: 250,
      event: {
        event_id: makeId(),
        step: 2,
        phase: "Specialist Tracks Dispatched",
        headline: "Schedule Dispatched",
        metric: "4 tracks",
        message:
          "Specialist lanes allocated on shared time axis. Circular flows and pass-through tracks run concurrently once data validation completes initial schema mapping.",
        timestamp: new Date().toISOString(),
        agent_id: "ORCHESTRATOR",
        action: "delegated",
        source: "SIMULATION",
      },
    },

    // --- TRACK 1: DATA_VALIDATION (T=400ms to T=1800ms) ---
    {
      delayMs: 400,
      event: {
        event_id: makeId(),
        step: 3,
        phase: "Data Validation Initiated",
        headline: "Schema Inspection",
        metric: `${totalRows.toLocaleString("en-US")} rows`,
        message: `Inspecting dataset structure and column coverage across ${fileCount} uploaded file(s).`,
        timestamp: new Date().toISOString(),
        agent_id: "DATA_VALIDATION",
        action: "started",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "DATA_VALIDATION", status: "reviewing" },
      agentDecisionUpdate: {
        agentId: "DATA_VALIDATION",
        decision: {
          task: "Inspecting column schema and data types",
          metric: `${totalRows.toLocaleString()} rows`,
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      delayMs: 900,
      event: {
        event_id: makeId(),
        step: 4,
        phase: "Schema Normalization",
        headline: "Tool: normalize_columns",
        metric: `${totalCols} columns mapped`,
        message: "Mapped core transaction fields: origin, destination, amount, and timestamp.",
        timestamp: new Date().toISOString(),
        agent_id: "DATA_VALIDATION",
        action: "tool",
        source: "SIMULATION",
        tool_call: {
          name: "normalize_columns",
          label: "Normalize Schema",
          outcome: "Mapped origin, destination, amount, and timestamp fields across input files.",
          duration_ms: 140,
        },
      },
      agentDecisionUpdate: {
        agentId: "DATA_VALIDATION",
        decision: {
          task: "Tool: normalize_columns",
          decision: "Mapped canonical fields (origin, destination, amount, timestamp)",
          metric: `${totalCols} cols`,
          timestamp: new Date().toISOString(),
        },
      },
    },

    // --- STAGE 2: DUAL-PRONGED PATTERN DISCOVERY (T=1200ms to T=2800ms) ---
    {
      delayMs: 1200,
      event: {
        event_id: makeId(),
        step: 5,
        phase: "Circular Flows Initiated",
        headline: "Graph Cycle Scan",
        metric: "nx.simple_cycles",
        message: "Building directed graph topology to trace candidate closed fund cycles.",
        timestamp: new Date().toISOString(),
        agent_id: "CIRCULAR_FLOWS",
        action: "started",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "CIRCULAR_FLOWS", status: "reviewing" },
      agentDecisionUpdate: {
        agentId: "CIRCULAR_FLOWS",
        decision: {
          task: "Building directed graph topology",
          metric: "nx.simple_cycles",
          timestamp: new Date().toISOString(),
        },
      },
      situationalStateUpdate: {
        stage: "discovery",
        stageIndex: 1,
        progressPct: 40,
        stageTitle: "Concurrent Pattern Extraction",
        executiveSummary:
          "The team has transitioned into concurrent pattern extraction. While graph algorithms search for closed loops that indicate round-tripping, flow velocity filters are actively screening account nodes for rapid pass-through conduit behavior.",
        advances: [
          { label: "Scan Mode", value: "Dual concurrent tracks" },
          { label: "Graph Nodes", value: `${currentCase.metrics.total_nodes_analyzed} accounts` },
          { label: "Status", value: "Tracing patterns" },
        ],
      },
    },
    {
      delayMs: 1400,
      event: {
        event_id: makeId(),
        step: 6,
        phase: "Rapid Pass-through Initiated",
        headline: "Flow Velocity Scan",
        metric: "48h window",
        message: "Scanning account nodes for rapid transit behavior with matched inflow/outflow ratios.",
        timestamp: new Date().toISOString(),
        agent_id: "PASSTHROUGH",
        action: "started",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "PASSTHROUGH", status: "reviewing" },
      agentDecisionUpdate: {
        agentId: "PASSTHROUGH",
        decision: {
          task: "Scanning transit velocity and dwell times",
          metric: "48h window",
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      delayMs: 1500,
      event: {
        event_id: makeId(),
        step: 7,
        phase: "Dataset Validation Completed",
        headline: "Dataset Normalized",
        metric: `${currentCase.metrics.total_nodes_analyzed} accounts`,
        message: `${totalRows.toLocaleString("en-US")} rows normalized with ${currentCase.metrics.total_nodes_analyzed} unique account nodes verified for graph analytics.`,
        timestamp: new Date().toISOString(),
        agent_id: "DATA_VALIDATION",
        action: "finding",
        source: "SIMULATION",
        evidence_refs: [{ kind: "dataset", id: "normalized", label: "Uploaded sample records" }],
      },
      agentDecisionUpdate: {
        agentId: "DATA_VALIDATION",
        decision: {
          task: "Verified schema consistency",
          decision: `${currentCase.metrics.total_nodes_analyzed} unique accounts confirmed`,
          metric: "Verified",
          timestamp: new Date().toISOString(),
          evidence_ref: { kind: "dataset", id: "normalized", label: "Uploaded sample records" },
        },
      },
    },
    {
      delayMs: 1800,
      event: {
        event_id: makeId(),
        step: 8,
        phase: "Data Validation Hand-off",
        headline: "Validation Returned",
        metric: "100% normalized",
        message: "Normalized data model and timestamp assumptions confirmed. Clean graph inputs released to downstream specialists.",
        timestamp: new Date().toISOString(),
        agent_id: "DATA_VALIDATION",
        action: "returned",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "DATA_VALIDATION", status: "returned" },
      agentDecisionUpdate: {
        agentId: "DATA_VALIDATION",
        decision: {
          task: "Input validation complete",
          decision: "100% normalized graph inputs released to team",
          metric: "Complete",
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      delayMs: 1950,
      event: {
        event_id: makeId(),
        step: 9,
        phase: "Pruning Linear Chains",
        headline: "Tool: prune_linear",
        metric: `${pruneEfficiency}% pruned`,
        message: "Pruned non-cyclic linear transfers to isolate bounded circular paths.",
        timestamp: new Date().toISOString(),
        agent_id: "CIRCULAR_FLOWS",
        action: "tool",
        source: "SIMULATION",
        tool_call: {
          name: "prune_linear_chains",
          label: "Prune Linear Chains",
          outcome: `Pruned non-branching linear chains, reducing search space by ${pruneEfficiency}%.`,
          duration_ms: 220,
        },
      },
      agentDecisionUpdate: {
        agentId: "CIRCULAR_FLOWS",
        decision: {
          task: "Tool: prune_linear_chains",
          decision: `Pruned non-cyclic linear transfers (${pruneEfficiency}% reduction)`,
          metric: `${pruneEfficiency}% pruned`,
          timestamp: new Date().toISOString(),
        },
      },
      situationalStateUpdate: {
        progressPct: 55,
      },
    },
    {
      delayMs: 2150,
      event: {
        event_id: makeId(),
        step: 10,
        phase: "Flow Ratio Analysis",
        headline: "Tool: match_flow_ratio",
        metric: "ratio ≥ 0.90",
        message: "Evaluated in/out volume parity and transit dwell time for bridge accounts.",
        timestamp: new Date().toISOString(),
        agent_id: "PASSTHROUGH",
        action: "tool",
        source: "SIMULATION",
        tool_call: {
          name: "match_flow_ratio",
          label: "Evaluate Flow Ratio",
          outcome: "Calculated inflow/outflow balance and velocity across suspected bridge nodes.",
          duration_ms: 180,
        },
      },
      agentDecisionUpdate: {
        agentId: "PASSTHROUGH",
        decision: {
          task: "Tool: match_flow_ratio",
          decision: "Calculated in/out volume ratios across all nodes",
          metric: "ratio ≥ 0.90",
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      delayMs: 2550,
      event: {
        event_id: makeId(),
        step: 11,
        phase: "Closed Path Candidate",
        headline: "Circular Path Found",
        metric: `${cycle?.length || 3}-step cycle`,
        message: `Isolated closed cycle involving ${cycle?.length || 3} accounts with estimated volume of ${formatCurrencyMXN(cycle?.estimated_volume || 0)}.`,
        timestamp: new Date().toISOString(),
        agent_id: "CIRCULAR_FLOWS",
        action: "finding",
        source: "SIMULATION",
        evidence_refs: [{ kind: "cycle", id: "0", label: "Simulated circular path" }],
      },
      agentDecisionUpdate: {
        agentId: "CIRCULAR_FLOWS",
        decision: {
          task: "Closed loop isolated",
          decision: `Closed path identified through ${cycle?.length || 3} accounts`,
          metric: formatCurrencyMXN(cycle?.estimated_volume || 0),
          timestamp: new Date().toISOString(),
          evidence_ref: { kind: "cycle", id: "0", label: "Simulated circular path" },
        },
      },
    },
    {
      delayMs: 2750,
      event: {
        event_id: makeId(),
        step: 12,
        phase: "Bridge Account Isolated",
        headline: "Bridge Node Flagged",
        metric: `${passRatioPct}% flow match`,
        message: `High-velocity bridge account ${passthrough?.account || "sample"} identified with matched funds within 18h window.`,
        timestamp: new Date().toISOString(),
        agent_id: "PASSTHROUGH",
        action: "finding",
        source: "SIMULATION",
        evidence_refs: [
          {
            kind: "passthrough",
            id: passthrough?.account || "sample",
            label: "Simulated bridge account",
          },
        ],
      },
      agentDecisionUpdate: {
        agentId: "PASSTHROUGH",
        decision: {
          task: "Bridge node isolated",
          decision: `High-velocity bridge account ${passthrough?.account || "sample"} flagged with ${passRatioPct}% flow match`,
          metric: `${passRatioPct}% match`,
          timestamp: new Date().toISOString(),
          evidence_ref: {
            kind: "passthrough",
            id: passthrough?.account || "sample",
            label: "Simulated bridge account",
          },
        },
      },
    },

    // --- STAGE 3: MULTI-PATTERN RISK SYNTHESIS (T=2800ms to T=4850ms) ---
    {
      delayMs: 2800,
      event: {
        event_id: makeId(),
        step: 13,
        phase: "Risk Review Initiated",
        headline: "Schedule Dependency Met",
        metric: "Pruned graph ready",
        message: "Triggered following Data Validation hand-off and pattern detection. Correlating multi-pattern findings against risk indicators.",
        timestamp: new Date().toISOString(),
        agent_id: "RISK_REVIEW",
        action: "started",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "RISK_REVIEW", status: "reviewing" },
      agentDecisionUpdate: {
        agentId: "RISK_REVIEW",
        decision: {
          task: "Cross-referencing loop and bridge findings",
          metric: "Pruned graph ready",
          timestamp: new Date().toISOString(),
        },
      },
      situationalStateUpdate: {
        stage: "synthesis",
        stageIndex: 2,
        progressPct: 75,
        stageTitle: "Multi-Pattern Risk Synthesis",
        executiveSummary:
          "Both primary pattern indicators have surfaced. The team is now cross-referencing the closed capital loops directly against the high-velocity bridge conduits to evaluate suspicious layering typologies and match Mexican AML regulatory thresholds.",
        advances: [
          { label: "Suspicious Vol.", value: formatCurrencyMXN(suspVol), isAlert: true },
          { label: "Cycles Found", value: `${currentCase.patterns.cycles.length} loop(s)`, isAlert: true },
          {
            label: "Bridge Accounts",
            value: `${currentCase.patterns.passthrough_accounts.length} conduit(s)`,
            isAlert: true,
          },
        ],
      },
    },
    {
      delayMs: 3100,
      event: {
        event_id: makeId(),
        step: 14,
        phase: "Circular Flows Returned",
        headline: "Flows Returned",
        metric: `${currentCase.patterns.cycles.length} loop(s)`,
        message: "Closed cycle topology and suspicious path accounts delivered to shared context.",
        timestamp: new Date().toISOString(),
        agent_id: "CIRCULAR_FLOWS",
        action: "returned",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "CIRCULAR_FLOWS", status: "returned" },
      agentDecisionUpdate: {
        agentId: "CIRCULAR_FLOWS",
        decision: {
          task: "Analysis concluded",
          decision: "Closed cycle topology and volume matrix delivered to orchestrator",
          metric: "Complete",
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      delayMs: 3300,
      event: {
        event_id: makeId(),
        step: 15,
        phase: "Pass-through Returned",
        headline: "Bridge Returned",
        metric: `${passthrough?.time_delta_hours || 18}h window`,
        message: "Pass-through account evidence and velocity metrics submitted for risk synthesis.",
        timestamp: new Date().toISOString(),
        agent_id: "PASSTHROUGH",
        action: "returned",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "PASSTHROUGH", status: "returned" },
      agentDecisionUpdate: {
        agentId: "PASSTHROUGH",
        decision: {
          task: "Analysis concluded",
          decision: "Pass-through account evidence and dwell metrics delivered to orchestrator",
          metric: "Complete",
          timestamp: new Date().toISOString(),
        },
      },
    },
    {
      delayMs: 3500,
      event: {
        event_id: makeId(),
        step: 16,
        phase: "AML Thresholds Assessment",
        headline: "Tool: evaluate_thresholds",
        metric: "UIF / GAFI flags",
        message: `Cross-referenced suspicious volume (${formatCurrencyMXN(suspVol)}) against Mexican AML typologies and threshold criteria.`,
        timestamp: new Date().toISOString(),
        agent_id: "RISK_REVIEW",
        action: "tool",
        source: "SIMULATION",
        tool_call: {
          name: "evaluate_thresholds",
          label: "Evaluate AML Thresholds",
          outcome: "Verified co-occurrence of circular routing and high-velocity pass-through conduit behavior.",
          duration_ms: 190,
        },
      },
      agentDecisionUpdate: {
        agentId: "RISK_REVIEW",
        decision: {
          task: "Tool: evaluate_thresholds",
          decision: "Verified co-occurrence against Mexican AML regulatory criteria",
          metric: "Thresholds met",
          timestamp: new Date().toISOString(),
        },
      },
      situationalStateUpdate: {
        progressPct: 85,
      },
    },
    {
      delayMs: 4050,
      event: {
        event_id: makeId(),
        step: 17,
        phase: "Risk Profile Formed",
        headline: "Risk Profile Mapped",
        metric: "High Risk Flag",
        message: "Combined findings indicate deliberate layering behavior. Recommended escalation notes and interface limitations prepared.",
        timestamp: new Date().toISOString(),
        agent_id: "RISK_REVIEW",
        action: "finding",
        source: "SIMULATION",
        evidence_refs: [{ kind: "overview", id: "risk", label: "Simulation overview" }],
      },
      agentDecisionUpdate: {
        agentId: "RISK_REVIEW",
        decision: {
          task: "Risk profile established",
          decision: "High Risk indicator flagged; layering behavior confirmed",
          metric: "High Risk",
          timestamp: new Date().toISOString(),
          evidence_ref: { kind: "overview", id: "risk", label: "Simulation overview" },
        },
      },
    },
    {
      delayMs: 4550,
      event: {
        event_id: makeId(),
        step: 18,
        phase: "Risk Review Returned",
        headline: "Review Returned",
        metric: "Audit notes ready",
        message: "Forensic notes, recommended human escalation steps, and clear simulation boundaries finalized for the orchestrator.",
        timestamp: new Date().toISOString(),
        agent_id: "RISK_REVIEW",
        action: "returned",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "RISK_REVIEW", status: "returned" },
      agentDecisionUpdate: {
        agentId: "RISK_REVIEW",
        decision: {
          task: "Review concluded",
          decision: "Compliance and human escalation recommendations returned",
          metric: "Complete",
          timestamp: new Date().toISOString(),
        },
      },
    },

    // --- FINAL PHASE: ORCHESTRATOR SYNTHESIS (T=4850ms) ---
    {
      delayMs: 4850,
      event: {
        event_id: makeId(),
        step: 19,
        phase: "Synthesizing Assessment",
        headline: "Orchestrator Synthesis",
        metric: "All 4 returned",
        message: "All four specialist reviews returned. Aggregating evidence into final forensic assessment and collapsing review lanes.",
        timestamp: new Date().toISOString(),
        agent_id: "ORCHESTRATOR",
        action: "synthesizing",
        source: "SIMULATION",
      },
      agentStatusUpdate: { agentId: "ORCHESTRATOR", status: "reviewing" },
      agentDecisionUpdate: {
        agentId: "ORCHESTRATOR",
        decision: {
          task: "Synthesizing executive forensic assessment",
          decision: "All 4 specialist dossiers unified",
          metric: "Synthesis",
          timestamp: new Date().toISOString(),
        },
      },
      situationalStateUpdate: {
        progressPct: 95,
      },
    },
  ];
}

function makeVerdict(currentCase: UploadResponse): VerdictEvent {
  return {
    case_id: currentCase.case_id,
    source: "SIMULATION",
    assessment_method: "FRONTEND_DEMO",
    assessment_status: "SUSPICIOUS_PATTERNS_DETECTED",
    risk_level: "ALTO",
    fraud_type: "Simulated circular flow and pass-through indicators",
    total_amount_mxn: currentCase.metrics.suspicious_volume_mxn,
    confidence_score: null,
    entities_involved: currentCase.subgraph.nodes.slice(0, 4).map((node) => node.id),
    pruned_leads_count: currentCase.metrics.pruned_edges_count,
    patterns_summary: {
      closed_cycles: currentCase.patterns.cycles.length,
      passthrough_accounts: currentCase.patterns.passthrough_accounts.length,
      pruning_efficiency_pct: currentCase.metrics.pruning_efficiency_pct,
    },
    legal_recommendation:
      "Demo only. In a real investigation, validate source records and supporting documents before deciding whether escalation or reporting is appropriate.",
    audit_summary_text:
      "Simulation complete. The interface demonstrates how a team of specialists concurrently executes forensic checks and returns connected findings to an orchestrator. The displayed patterns and risk level are illustrative and are not the result of a fraud analysis.",
    limitations: [
      "This is a frontend workflow simulation.",
      "Pattern findings and the final risk level are illustrative.",
      "Uploaded values are used only to make the preview feel connected to the selected files.",
      "No backend, AI model, sanctions source, or fraud detection service was called.",
    ],
    completed_at: new Date().toISOString(),
  };
}

export function useAgentSimulation(): UseAgentSimulationReturn {
  const [currentCase, setCurrentCase] = useState<UploadResponse | null>(null);
  const [thoughts, setThoughts] = useState<ThoughtEvent[]>([]);
  const [verdict, setVerdict] = useState<VerdictEvent | null>(null);
  const [statuses, setStatuses] = useState<AgentStatuses>(waitingStatuses);
  const [situationalState, setSituationalState] = useState<TeamSituationalState>(initialSituationalState);
  const [agentDecisions, setAgentDecisions] = useState<Record<AgentId, AgentDecision>>(initialAgentDecisions);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  const timersRef = useRef<Array<ReturnType<typeof setTimeout>>>([]);
  const runRef = useRef(0);
  const userSelectedRef = useRef(false);

  const clearAllTimers = () => {
    timersRef.current.forEach((timer) => clearTimeout(timer));
    timersRef.current = [];
  };

  const resetSimulation = useCallback(() => {
    runRef.current += 1;
    clearAllTimers();
    userSelectedRef.current = false;
    setCurrentCase(null);
    setThoughts([]);
    setVerdict(null);
    setStatuses(waitingStatuses());
    setSituationalState(initialSituationalState());
    setAgentDecisions(initialAgentDecisions());
    setIsPreparing(false);
    setIsRunning(false);
    setError(null);
    setSelectedStepId(null);
  }, []);

  useEffect(() => () => {
    runRef.current += 1;
    clearAllTimers();
  }, []);

  const handleSelectStep = useCallback((id: string | null) => {
    userSelectedRef.current = true;
    setSelectedStepId(id);
  }, []);

  const startSimulation = useCallback(
    async (selectedFiles: File[]) => {
      resetSimulation();
      const currentRun = runRef.current;
      setIsPreparing(true);

      try {
        const parsed = await Promise.all(selectedFiles.map(parseFile));
        if (runRef.current !== currentRun) return;

        const nextCase = makeCase(parsed);
        const scheduledSteps = buildConcurrentSchedule(nextCase);

        setCurrentCase(nextCase);
        setIsPreparing(false);
        setIsRunning(true);

        // Schedule every step on the shared time axis
        scheduledSteps.forEach((scheduled) => {
          const timer = setTimeout(() => {
            if (runRef.current !== currentRun) return;

            setThoughts((prev) => [...prev, scheduled.event]);

            // Auto-track the latest step if user hasn't explicitly selected one
            if (!userSelectedRef.current) {
              setSelectedStepId(scheduled.event.event_id || null);
            }

            if (scheduled.agentStatusUpdate) {
              const { agentId, status } = scheduled.agentStatusUpdate;
              setStatuses((prev) => ({
                ...prev,
                [agentId]: status,
              }));
            }

            if (scheduled.agentDecisionUpdate) {
              const { agentId, decision } = scheduled.agentDecisionUpdate;
              setAgentDecisions((prev) => ({
                ...prev,
                [agentId]: decision,
              }));
            }

            if (scheduled.situationalStateUpdate) {
              setSituationalState((prev) => ({
                ...prev,
                ...scheduled.situationalStateUpdate,
              }));
            }
          }, scheduled.delayMs);

          timersRef.current.push(timer);
        });

        // Schedule final verdict transition at T=5400ms
        const finalTimer = setTimeout(() => {
          if (runRef.current !== currentRun) return;

          const finalVerdict = makeVerdict(nextCase);
          setVerdict(finalVerdict);
          setStatuses((prev) => ({ ...prev, ORCHESTRATOR: "complete" }));
          setAgentDecisions((prev) => ({
            ...prev,
            ORCHESTRATOR: {
              task: "Forensic assessment published",
              decision: "High Risk verdict reached; audio synthesis ready",
              metric: "Complete",
              timestamp: new Date().toISOString(),
            },
          }));
          setSituationalState({
            stage: "verdict",
            stageIndex: 3,
            progressPct: 100,
            stageTitle: "Forensic Adjudication & Verdict",
            executiveSummary: `Investigation complete. The team has consolidated all findings into a final forensic assessment. Clear indicators of structured circular layering and bridge routing were detected, accounting for ${formatCurrencyMXN(
              nextCase.metrics.suspicious_volume_mxn
            )} in flagged operations.`,
            advances: [
              { label: "Risk Assessment", value: "ALTO (High Risk)", isAlert: true },
              {
                label: "Flagged Volume",
                value: formatCurrencyMXN(nextCase.metrics.suspicious_volume_mxn),
                isAlert: true,
              },
              {
                label: "Entities Flagged",
                value: `${nextCase.metrics.suspicious_nodes_count} accounts`,
                isAlert: true,
              },
              {
                label: "Pruning Efficiency",
                value: `${nextCase.metrics.pruning_efficiency_pct}% noise pruned`,
              },
            ],
          });
          setIsRunning(false);
        }, 5400);

        timersRef.current.push(finalTimer);
      } catch (cause: unknown) {
        if (runRef.current !== currentRun) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "The files could not be prepared for simulation."
        );
        setIsPreparing(false);
      }
    },
    [resetSimulation]
  );

  const selectedStep = useMemo(() => {
    if (!thoughts.length) return null;
    if (!selectedStepId) return thoughts[thoughts.length - 1];
    return thoughts.find((s) => s.event_id === selectedStepId) || thoughts[thoughts.length - 1];
  }, [thoughts, selectedStepId]);

  return {
    currentCase,
    thoughts,
    verdict,
    statuses,
    situationalState,
    agentDecisions,
    isPreparing,
    isRunning,
    error,
    selectedStepId,
    setSelectedStepId: handleSelectStep,
    selectedStep,
    startSimulation,
    resetSimulation,
  };
}
