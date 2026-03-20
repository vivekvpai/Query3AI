from neo4j import GraphDatabase
from config.settings import settings
import uuid

class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def create_node(self, label: str, properties: dict) -> dict:
        node_id = str(uuid.uuid4())
        props_with_id = {"node_id": node_id, **properties}
        
        query = f"CREATE (n:{label} $props) RETURN properties(n) AS props"
        with self.driver.session() as session:
            result = session.run(query, props=props_with_id)
            record = result.single()
            if record:
                 return record["props"]
            return {}

    def get_nodes(self, label: str) -> list[dict]:
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
            
    def execute_query(self, query: str, parameters: dict = None):
        """Executes a custom query, useful for making relationships."""
        with self.driver.session() as session:
            return [record.data() for record in session.run(query, parameters or {})]

neo4j_client = Neo4jClient()
