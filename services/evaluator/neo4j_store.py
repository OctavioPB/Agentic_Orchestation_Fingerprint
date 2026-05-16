"""Neo4j graph store — persists interaction graph and fingerprint relationships.

Schema:
    (Candidate {candidate_id})-[:INTERACTED_WITH {count, avg_latency_ms}]->(Agent {name})
    (Session {session_id})-[:PRODUCED]->(Fingerprint {session_id})
    (Candidate)-[:BENCHMARKS_AGAINST]->(SeniorProfile {profile_id})

The neo4j driver is imported lazily so unit tests do not require a running graph DB.
Pass a pre-built driver to the constructor for test injection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from services.evaluator.fingerprint import OrchestraFingerprint

logger = structlog.get_logger(__name__)


class Neo4jStore:
    """Thin wrapper around the Neo4j Bolt driver.

    Injects a driver for testing; otherwise builds one lazily from env vars.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        *,
        driver: Any | None = None,
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = driver

    def _get_driver(self) -> Any:
        if self._driver is not None:
            return self._driver
        from neo4j import GraphDatabase  # lazy import

        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()

    # ------------------------------------------------------------------
    # Fingerprint persistence
    # ------------------------------------------------------------------

    def persist_fingerprint(self, fingerprint: OrchestraFingerprint) -> None:
        """Upsert all nodes and relationships for a completed fingerprint."""
        driver = self._get_driver()
        with driver.session() as session:
            session.execute_write(self._write_fingerprint, fingerprint)
        logger.info(
            "neo4j_fingerprint_persisted",
            session_id=fingerprint.session_id,
        )

    @staticmethod
    def _write_fingerprint(tx: Any, fingerprint: OrchestraFingerprint) -> None:
        # Candidate node
        tx.run(
            "MERGE (c:Candidate {candidate_id: $cid})",
            cid=fingerprint.candidate_id,
        )
        # Session node
        tx.run(
            "MERGE (s:Session {session_id: $sid}) "
            "SET s.scenario_id = $scenario_id",
            sid=fingerprint.session_id,
            scenario_id=fingerprint.scenario_id,
        )
        # Fingerprint node
        tx.run(
            """
            MERGE (f:Fingerprint {session_id: $sid})
            SET f.style_cluster = $cluster,
                f.efficiency_ratio = $eff,
                f.trust_calibration = $trust,
                f.correction_velocity = $vel,
                f.decomposition_score = $decomp,
                f.chaos_resilience = $chaos,
                f.benchmark_delta = $delta
            """,
            sid=fingerprint.session_id,
            cluster=fingerprint.style_cluster,
            eff=fingerprint.scores.efficiency_ratio,
            trust=fingerprint.scores.trust_calibration,
            vel=fingerprint.scores.correction_velocity,
            decomp=fingerprint.scores.decomposition_score,
            chaos=fingerprint.scores.chaos_resilience,
            delta=fingerprint.benchmark_delta,
        )
        # (Session)-[:PRODUCED]->(Fingerprint)
        tx.run(
            """
            MATCH (s:Session {session_id: $sid})
            MATCH (f:Fingerprint {session_id: $sid})
            MERGE (s)-[:PRODUCED]->(f)
            """,
            sid=fingerprint.session_id,
        )
        # (Candidate)-[:HAD_SESSION]->(Session)
        tx.run(
            """
            MATCH (c:Candidate {candidate_id: $cid})
            MATCH (s:Session {session_id: $sid})
            MERGE (c)-[:HAD_SESSION]->(s)
            """,
            cid=fingerprint.candidate_id,
            sid=fingerprint.session_id,
        )
        # Interaction graph edges
        Neo4jStore._write_interaction_graph(tx, fingerprint)

    @staticmethod
    def _write_interaction_graph(tx: Any, fingerprint: OrchestraFingerprint) -> None:
        for edge in fingerprint.interaction_graph.edges:
            if edge.source == "human":
                # (Candidate)-[:INTERACTED_WITH]->(Agent)
                tx.run(
                    """
                    MATCH (c:Candidate {candidate_id: $cid})
                    MERGE (a:Agent {name: $agent})
                    MERGE (c)-[r:INTERACTED_WITH {session_id: $sid}]->(a)
                    SET r.count = $count, r.correction_count = $corrections
                    """,
                    cid=fingerprint.candidate_id,
                    agent=edge.target,
                    sid=fingerprint.session_id,
                    count=edge.message_count,
                    corrections=edge.correction_count,
                )
            elif edge.target == "human":
                # (Agent)-[:RESPONDED_TO]->(Candidate)
                tx.run(
                    """
                    MATCH (c:Candidate {candidate_id: $cid})
                    MERGE (a:Agent {name: $agent})
                    MERGE (a)-[r:RESPONDED_TO {session_id: $sid}]->(c)
                    SET r.count = $count, r.avg_latency_ms = $lat
                    """,
                    cid=fingerprint.candidate_id,
                    agent=edge.source,
                    sid=fingerprint.session_id,
                    count=edge.message_count,
                    lat=edge.avg_latency_ms,
                )

    # ------------------------------------------------------------------
    # Benchmark relationships
    # ------------------------------------------------------------------

    def link_benchmark_profiles(
        self, candidate_id: str, profile_ids: list[str]
    ) -> None:
        """Create (Candidate)-[:BENCHMARKS_AGAINST]->(SeniorProfile) edges."""
        driver = self._get_driver()
        with driver.session() as session:
            for profile_id in profile_ids:
                session.execute_write(
                    self._write_benchmark_link, candidate_id, profile_id
                )

    @staticmethod
    def _write_benchmark_link(tx: Any, candidate_id: str, profile_id: str) -> None:
        tx.run(
            """
            MATCH (c:Candidate {candidate_id: $cid})
            MERGE (p:SeniorProfile {profile_id: $pid})
            MERGE (c)-[:BENCHMARKS_AGAINST]->(p)
            """,
            cid=candidate_id,
            pid=profile_id,
        )
