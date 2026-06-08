import os
from neo4j import GraphDatabase

uri = "neo4j+s://0b37bab3.databases.neo4j.io"
user = "neo4j"
password = "vOB1ffNEOCTYeVJgYlKmm4E2hzwVq6lAaJifNsCWL9w"

print(f"Testing Neo4j Aura connection...")
print(f"URI: {uri}")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    print("✅ Connection successful!")
    
    with driver.session() as session:
        result = session.run("RETURN 1 as test")
        print(f"✅ Query test: {result.single()['test']}")
    
    driver.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nPossible solutions:")
    print("1. Check if Neo4j Aura instance is running")
    print("2. Verify the URI format (should be neo4j+s://...)")
    print("3. Check network connectivity")
    print("4. Verify credentials")
