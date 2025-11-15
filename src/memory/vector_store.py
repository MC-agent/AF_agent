import os
from pymilvus import MilvusClient

uri = os.getenv("MILVUS_URI", "http://localhost:19530")

client = MilvusClient(uri=uri)

# 예시: 헬스 체크
print(client.list_collections())
