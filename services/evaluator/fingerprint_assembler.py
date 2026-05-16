"""Fingerprint assembly pipeline — orchestrates all evaluator components.

``assemble_fingerprint`` is the single entry point. It runs, in order:
  1. Embedding ETL → Qdrant (if not already done)
  2. Style classification via KNN over benchmark profiles
  3. Benchmark delta computation
  4. Shadow Agent evaluation (prompt scores, reasoning trace, style narrative)
  5. All five scoring functions
  6. Interaction graph construction from raw events
  7. Report markdown generation via a second Claude call

Returns a fully-populated ``OrchestraFingerprint``.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from services.evaluator.agents.llm_client import LLMClient
from services.evaluator.embedding_etl import EmbeddingETL
from services.evaluator.embeddings import (
    EmbeddingClient,
    compute_benchmark_delta,
    compute_centroid,
)
from services.evaluator.fingerprint import (
    GraphEdge,
    GraphNode,
    InteractionGraph,
    OrchestraFingerprint,
    ScoreSet,
)
from services.evaluator.qdrant_store import QdrantStore
from services.evaluator.scoring import (
    chaos_resilience,
    correction_velocity,
    decomposition_score,
    efficiency_ratio,
    trust_calibration,
)
from services.evaluator.shadow_agent import ShadowAgent
from services.evaluator.style_classifier import StyleClassifier

logger = structlog.get_logger(__name__)

_REPORT_MODEL = "claude-sonnet-4-6"
_BENCHMARKS_DIR = (
    Path(__file__).parent.parent.parent / "data" / "benchmarks" / "senior_engineer_profiles"
)

_REPORT_SYSTEM_PROMPT = """\
You are a technical assessment report writer for orchid, a next-generation
engineering leadership assessment platform.

You will receive a structured JSON summary of a candidate's assessment session.
Write a concise, professional 3–5 paragraph Markdown report for hiring reviewers.

Guidelines:
- Focus on HOW the candidate led their AI team, not technical correctness.
- Reference specific scores and what they signal about leadership style.
- Name the style cluster and explain what it predicts about the candidate in a team.
- Note the chaos event and how the candidate responded.
- End with 2–3 actionable observations for the hiring team.
- Use clear Markdown headings. Keep it under 500 words.
- Never use the candidate's name if it appears in the data — use "the candidate".
"""


# ---------------------------------------------------------------------------
# Session loader helpers
# ---------------------------------------------------------------------------


def load_session(session_data: dict) -> tuple[str, str, str, list[dict]]:
    """Extract (session_id, candidate_id, scenario_id, events) from raw dict."""
    return (
        session_data["session_id"],
        session_data["candidate_id"],
        session_data["scenario_id"],
        session_data["events"],
    )


# ---------------------------------------------------------------------------
# Interaction graph builder (pure — no LLM needed)
# ---------------------------------------------------------------------------


def build_interaction_graph(events: list[dict]) -> InteractionGraph:
    """Construct an InteractionGraph from raw telemetry events."""
    human_id = "human"
    agent_names: set[str] = set()
    edge_data: dict[tuple[str, str], dict] = {}

    for event in events:
        etype = event.get("event_type", "")
        payload = event.get("payload", {})
        agent = payload.get("agent")
        if not agent:
            continue

        agent_names.add(agent)

        if etype == "PROMPT_SENT":
            key = (human_id, agent)
            rec = edge_data.setdefault(key, {"messages": 0, "corrections": 0, "latencies": []})
            rec["messages"] += 1

        elif etype == "AGENT_RESPONSE":
            latency_ms = payload.get("latency_ms")
            key = (agent, human_id)
            rec = edge_data.setdefault(key, {"messages": 0, "corrections": 0, "latencies": []})
            rec["messages"] += 1
            if latency_ms is not None:
                rec["latencies"].append(float(latency_ms))

        elif etype == "CORRECTION_ISSUED":
            key = (human_id, agent)
            rec = edge_data.setdefault(key, {"messages": 0, "corrections": 0, "latencies": []})
            rec["corrections"] += 1

    nodes: list[GraphNode] = [
        GraphNode(id=human_id, label="Candidate", node_type="human")
    ]
    for name in sorted(agent_names):
        nodes.append(
            GraphNode(id=name, label=name, node_type="agent", agent_name=name)
        )

    edges: list[GraphEdge] = []
    for (source, target), rec in edge_data.items():
        avg_lat = (sum(rec["latencies"]) / len(rec["latencies"])) if rec["latencies"] else None
        edges.append(
            GraphEdge(
                source=source,
                target=target,
                message_count=rec["messages"],
                correction_count=rec["corrections"],
                avg_latency_ms=round(avg_lat, 1) if avg_lat is not None else None,
            )
        )

    return InteractionGraph(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------


async def assemble_fingerprint(
    session_data: dict,
    llm_client: LLMClient,
    embedding_client: EmbeddingClient,
    qdrant_store: QdrantStore,
    *,
    benchmarks_dir: Path = _BENCHMARKS_DIR,
    skip_etl: bool = False,
) -> OrchestraFingerprint:
    """Assemble a complete OrchestraFingerprint from a raw session dict.

    Parameters
    ----------
    session_data:    Raw session JSON dict (as stored in data/synthetic/).
    llm_client:      AnthropicLLMClient for Shadow Agent + report generation.
    embedding_client: OpenAIEmbeddingClient for ETL.
    qdrant_store:    QdrantStore for session vectors.
    benchmarks_dir:  Directory containing benchmark profile JSON files.
    skip_etl:        If True, assume embeddings are already in Qdrant (saves cost).
    """
    session_id, candidate_id, scenario_id, events = load_session(session_data)

    logger.info(
        "fingerprint_assembly_start",
        session_id=session_id,
        scenario_id=scenario_id,
        events=len(events),
    )

    # ------------------------------------------------------------------
    # 1. Embedding ETL
    # ------------------------------------------------------------------
    if not skip_etl:
        etl = EmbeddingETL(embedding_client=embedding_client, qdrant_store=qdrant_store)
        etl_result = await etl.process_session(session_id, events)
        logger.info("fingerprint_etl_done", points=etl_result.points_upserted)
    else:
        logger.info("fingerprint_etl_skipped")

    # ------------------------------------------------------------------
    # 2. Style classification + benchmark delta
    # ------------------------------------------------------------------
    vectors = await qdrant_store.get_session_vectors(session_id)
    if vectors:
        session_centroid = compute_centroid(vectors)
        classifier = StyleClassifier.from_directory(benchmarks_dir)
        style_cluster = classifier.classify(session_centroid)

        benchmark_centroids = [p.centroid for p in classifier._profiles]  # noqa: SLF001
        b_delta = compute_benchmark_delta(session_centroid, benchmark_centroids)
    else:
        logger.warning("fingerprint_no_vectors", session_id=session_id)
        style_cluster = None
        b_delta = None

    # ------------------------------------------------------------------
    # 3. Shadow Agent evaluation
    # ------------------------------------------------------------------
    shadow = ShadowAgent(llm_client=llm_client)
    shadow_result = await shadow.evaluate(events)

    if shadow_result.style_cluster is not None and style_cluster is None:
        style_cluster = shadow_result.style_cluster

    # ------------------------------------------------------------------
    # 4. Scoring
    # ------------------------------------------------------------------
    scores = ScoreSet(
        efficiency_ratio=efficiency_ratio(events, scenario_id),
        trust_calibration=trust_calibration(events),
        correction_velocity=correction_velocity(events),
        decomposition_score=decomposition_score(shadow_result.prompt_scores),
        chaos_resilience=chaos_resilience(events),
    )

    # ------------------------------------------------------------------
    # 5. Interaction graph
    # ------------------------------------------------------------------
    interaction_graph = build_interaction_graph(events)

    # ------------------------------------------------------------------
    # 6. Report markdown (second Claude call)
    # ------------------------------------------------------------------
    report_md = await _generate_report(
        llm_client=llm_client,
        session_id=session_id,
        scenario_id=scenario_id,
        scores=scores,
        style_cluster=style_cluster,
        style_narrative=shadow_result.style_narrative,
        reasoning_trace=shadow_result.reasoning_trace,
        benchmark_delta=b_delta,
    )

    fingerprint = OrchestraFingerprint(
        session_id=session_id,
        candidate_id=candidate_id,
        scenario_id=scenario_id,
        scores=scores,
        style_cluster=style_cluster,
        reasoning_trace=shadow_result.reasoning_trace,
        interaction_graph=interaction_graph,
        benchmark_delta=b_delta,
        report_markdown=report_md,
    )

    logger.info(
        "fingerprint_assembly_complete",
        session_id=session_id,
        is_complete=fingerprint.is_complete,
        style_cluster=style_cluster,
    )
    return fingerprint


# ---------------------------------------------------------------------------
# Report generation helper
# ---------------------------------------------------------------------------


async def _generate_report(
    llm_client: LLMClient,
    session_id: str,
    scenario_id: str,
    scores: ScoreSet,
    style_cluster: str | None,
    style_narrative: str,
    reasoning_trace: list[str],
    benchmark_delta: float | None,
) -> str:
    summary = {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "style_cluster": style_cluster,
        "scores": {
            "efficiency_ratio": scores.efficiency_ratio,
            "trust_calibration": scores.trust_calibration,
            "correction_velocity": scores.correction_velocity,
            "decomposition_score": scores.decomposition_score,
            "chaos_resilience": scores.chaos_resilience,
        },
        "benchmark_delta": benchmark_delta,
        "style_narrative": style_narrative,
        "reasoning_trace": reasoning_trace,
    }

    messages = [
        {"role": "system", "content": _REPORT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Generate the assessment report for the following session:\n\n"
                + json.dumps(summary, indent=2)
            ),
        },
    ]

    response = await llm_client.acomplete(
        messages=messages,
        model=_REPORT_MODEL,
        max_tokens=1024,
        temperature=0.4,
    )

    logger.info(
        "report_generation_complete",
        model_version=response.model,
        latency_ms=response.latency_ms,
        token_count=response.total_tokens,
    )
    return response.content
