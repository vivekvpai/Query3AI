from neo4j import GraphDatabase
from query3ai.config.settings import settings

# Allowlisted Neo4j labels to prevent Cypher injection
_VALID_LABELS = frozenset({"Document", "Chapter", "Section", "Chunk"})


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            notifications_min_severity="OFF",
        )

    def close(self):
        self.driver.close()

    @staticmethod
    def _validate_label(label: str) -> str:
        """Validates that a label is in the allowlist to prevent Cypher injection."""
        if label not in _VALID_LABELS:
            raise ValueError(
                f"Invalid Neo4j label '{label}'. Allowed: {', '.join(sorted(_VALID_LABELS))}"
            )
        return label

    def create_node(self, label: str, properties: dict) -> dict:
        """Creates a node with the given label and properties. Caller must supply 'node_id'."""
        label = self._validate_label(label)
        query = f"CREATE (n:{label} $props) RETURN properties(n) AS props"
        with self.driver.session() as session:
            result = session.run(query, props=properties)
            record = result.single()
            return record["props"] if record else {}

    def get_nodes(self, label: str) -> list[dict]:
        label = self._validate_label(label)
        query = f"MATCH (n:{label}) RETURN properties(n) AS props"
        with self.driver.session() as session:
            result = session.run(query)
            return [record["props"] for record in result]

    def delete_node(self, node_id: str):
        query = "MATCH (n {node_id: $id}) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query, id=node_id)

    def clear_all(self):
        query = "MATCH (n) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query)

    def execute_query(self, query: str, parameters: dict | None = None):
        """Executes a custom Cypher query."""
        with self.driver.session() as session:
            return [record.data() for record in session.run(query, parameters or {})]


neo4j_client = Neo4jClient()
