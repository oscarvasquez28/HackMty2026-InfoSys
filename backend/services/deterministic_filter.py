from typing import Dict, Any, List, Set, Tuple
import polars as pl
import networkx as nx
from backend.core.config import settings


def build_transaction_graph(df: pl.DataFrame) -> nx.DiGraph:
    """
    Constructs a directed NetworkX graph from a Polars DataFrame with columns:
    ['origin', 'destination', 'amount', 'timestamp']
    """
    G = nx.DiGraph()

    # Iterate through rows or iterate over dict slices for fast network construction
    rows = df.select(["origin", "destination", "amount", "timestamp"]).to_dicts()

    for row in rows:
        u = str(row["origin"])
        v = str(row["destination"])
        amount = float(row["amount"])
        timestamp = float(row["timestamp"])

        if not G.has_node(u):
            G.add_node(u, total_in=0.0, total_out=0.0, in_timestamps=[], out_timestamps=[])
        if not G.has_node(v):
            G.add_node(v, total_in=0.0, total_out=0.0, in_timestamps=[], out_timestamps=[])

        # Update node stats
        G.nodes[u]["total_out"] += amount
        G.nodes[u]["out_timestamps"].append(timestamp)

        G.nodes[v]["total_in"] += amount
        G.nodes[v]["in_timestamps"].append(timestamp)

        if G.has_edge(u, v):
            edge_data = G[u][v]
            edge_data["amount"] += amount
            edge_data["count"] += 1
            edge_data["timestamps"].append(timestamp)
        else:
            G.add_edge(
                u,
                v,
                amount=amount,
                count=1,
                timestamps=[timestamp],
                reasons=[]
            )

    return G


def detect_closed_cycles(
    G: nx.DiGraph, max_cycle_length: int = 5
) -> Tuple[List[List[str]], Set[str], Set[Tuple[str, str]]]:
    """
    Identifies closed directed cycles of length between 2 and max_cycle_length.
    Returns:
        - List of cycles (each cycle is a list of node IDs)
        - Set of suspicious nodes involved in cycles
        - Set of suspicious directed edges (u, v) involved in cycles
    """
    detected_cycles: List[List[str]] = []
    cycle_nodes: Set[str] = set()
    cycle_edges: Set[Tuple[str, str]] = set()

    # NetworkX simple_cycles generates elementary cycles
    try:
        raw_cycles = nx.simple_cycles(G)
        for c in raw_cycles:
            # We filter by max_cycle_length to prevent deep path computational stalls
            if 2 <= len(c) <= max_cycle_length:
                detected_cycles.append(c)
                for node in c:
                    cycle_nodes.add(node)
                for i in range(len(c)):
                    u = c[i]
                    v = c[(i + 1) % len(c)]
                    cycle_edges.add((u, v))
            elif len(c) > max_cycle_length:
                # Continue generator without deep exploration
                continue
    except Exception:
        # Fallback if graph is exceedingly complex
        pass

    return detected_cycles, cycle_nodes, cycle_edges


def detect_passthrough_accounts(
    G: nx.DiGraph,
    ratio_threshold: float = 0.90,
    window_hours: float = 48.0
) -> Tuple[List[Dict[str, Any]], Set[str], Set[Tuple[str, str]]]:
    """
    Detects layering / mule / pass-through accounts where:
    - Both incoming and outgoing flows exist (> 0)
    - The retention or pass-through ratio (min(in, out) / max(in, out) >= 0.90 or out / in >= 0.90)
    - Inflow and outflow occur within the temporal window (< 48 hours).
    """
    passthrough_accounts: List[Dict[str, Any]] = []
    pt_nodes: Set[str] = set()
    pt_edges: Set[Tuple[str, str]] = set()

    for node, data in G.nodes(data=True):
        total_in = data.get("total_in", 0.0)
        total_out = data.get("total_out", 0.0)
        in_ts = data.get("in_timestamps", [])
        out_ts = data.get("out_timestamps", [])

        if total_in > 0 and total_out > 0 and in_ts and out_ts:
            ratio = min(total_in, total_out) / max(total_in, total_out)
            # Check if output is at least 90% of input or flow matched >= 90%
            if ratio >= ratio_threshold:
                earliest_in = min(in_ts)
                latest_out = max(out_ts)
                # Temporal difference check
                time_delta = abs(latest_out - earliest_in)
                if time_delta <= window_hours:
                    account_meta = {
                        "account": node,
                        "total_in": round(total_in, 2),
                        "total_out": round(total_out, 2),
                        "ratio": round(ratio, 4),
                        "time_delta_hours": round(time_delta, 2),
                    }
                    passthrough_accounts.append(account_meta)
                    pt_nodes.add(node)

                    # Mark adjacent in/out edges as suspicious
                    for pred in G.predecessors(node):
                        pt_edges.add((pred, node))
                    for succ in G.successors(node):
                        pt_edges.add((node, succ))

    return passthrough_accounts, pt_nodes, pt_edges


def apply_deterministic_filter(
    df: pl.DataFrame,
    max_cycle_length: int = settings.MAX_CYCLE_LENGTH,
    ratio_threshold: float = settings.PASS_THROUGH_RATIO_THRESHOLD,
    window_hours: float = settings.PASS_THROUGH_WINDOW_HOURS,
) -> Dict[str, Any]:
    """
    Main deterministic filtering pipeline:
    1. Builds directed graph using NetworkX.
    2. Runs cycle detection and pass-through account algorithms.
    3. Prunes non-suspicious transactions.
    4. Returns subgraphs and forensic analysis data in dict format.
    """
    G = build_transaction_graph(df)

    cycles, cycle_nodes, cycle_edges = detect_closed_cycles(G, max_cycle_length)
    passthrough_list, pt_nodes, pt_edges = detect_passthrough_accounts(
        G, ratio_threshold, window_hours
    )

    all_suspicious_nodes = cycle_nodes.union(pt_nodes)
    all_suspicious_edges = cycle_edges.union(pt_edges)

    # Format nodes for output
    nodes_output: List[Dict[str, Any]] = []
    for node_id in all_suspicious_nodes:
        node_data = G.nodes[node_id]
        reasons = []
        if node_id in cycle_nodes:
            reasons.append("CIRCULAR_FLOW_CYCLE")
        if node_id in pt_nodes:
            reasons.append("HIGH_VELOCITY_PASSTHROUGH_90PCT")

        # Risk score calculation
        risk_score = 0.5
        if "CIRCULAR_FLOW_CYCLE" in reasons:
            risk_score += 0.3
        if "HIGH_VELOCITY_PASSTHROUGH_90PCT" in reasons:
            risk_score += 0.2
        risk_score = min(round(risk_score, 2), 1.0)

        nodes_output.append({
            "id": node_id,
            "total_in": round(node_data.get("total_in", 0.0), 2),
            "total_out": round(node_data.get("total_out", 0.0), 2),
            "in_degree": G.in_degree(node_id),
            "out_degree": G.out_degree(node_id),
            "reasons": reasons,
            "risk_score": risk_score,
        })

    # Format edges for output
    edges_output: List[Dict[str, Any]] = []
    suspicious_volume = 0.0

    for u, v in all_suspicious_edges:
        if G.has_edge(u, v):
            edge_data = G[u][v]
            reasons = []
            if (u, v) in cycle_edges:
                reasons.append("CYCLE_STEP")
            if (u, v) in pt_edges:
                reasons.append("PASSTHROUGH_BRIDGE")

            amount = round(edge_data.get("amount", 0.0), 2)
            suspicious_volume += amount

            edges_output.append({
                "source": u,
                "target": v,
                "amount": amount,
                "count": edge_data.get("count", 1),
                "timestamps": edge_data.get("timestamps", []),
                "reasons": reasons,
            })

    total_edges = G.number_of_edges()
    total_nodes = G.number_of_nodes()
    pruned_edges_count = total_edges - len(edges_output)
    pruned_nodes_count = total_nodes - len(nodes_output)

    # Format cycles for clean response
    formatted_cycles = []
    for c in cycles:
        cycle_amount = 0.0
        for i in range(len(c)):
            u, v = c[i], c[(i + 1) % len(c)]
            if G.has_edge(u, v):
                cycle_amount += G[u][v].get("amount", 0.0)
        formatted_cycles.append({
            "path": c + [c[0]],
            "length": len(c),
            "estimated_volume": round(cycle_amount, 2),
        })

    result = {
        "subgraph": {
            "nodes": nodes_output,
            "edges": edges_output,
        },
        "metrics": {
            "total_nodes_analyzed": total_nodes,
            "suspicious_nodes_count": len(nodes_output),
            "pruned_nodes_count": pruned_nodes_count,
            "total_edges_analyzed": total_edges,
            "suspicious_edges_count": len(edges_output),
            "pruned_edges_count": pruned_edges_count,
            "suspicious_volume_mxn": round(suspicious_volume, 2),
            "detected_cycles_count": len(cycles),
            "passthrough_accounts_count": len(passthrough_list),
            "pruning_efficiency_pct": round(
                (pruned_edges_count / total_edges * 100) if total_edges > 0 else 0.0, 2
            ),
        },
        "patterns": {
            "cycles": formatted_cycles,
            "passthrough_accounts": passthrough_list,
        },
    }

    return result
