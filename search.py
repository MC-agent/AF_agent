from pymilvus import MilvusClient
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from openai import OpenAI
from dotenv import load_dotenv
import os
import pdb

load_dotenv()


llm = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPENROUTER_API_KEY"),
)

client = MilvusClient(uri='http://milvus-standalone-name:19530')
embeddings = OpenAIEmbeddings(
  model="text-embedding-3-small",
)

def RAG(query:str, limit:int=5):
    query_embedding = embeddings.embed_query(query) ### 자연어 질문에 대한 vector embedding 실행
    res = client.search(
        collection_name='jeonsae',
        data =[query_embedding],
        output_fields=["sentence"],
        limit=limit
    )

    ### 'jeonsae'라는 collection에서 query_embedding 과 유사한 것을 vector에서 찾고 "sentence"라는 필드만 출력한다.
    # pdb.set_trace()
    return res

def print_results(query: str, results: list, limit: int = 5):
    """검색 결과의 내용만 출력하는 함수"""
    if not results or len(results) == 0:
        return
    
    # Milvus search 결과 구조 처리
    # results는 리스트의 리스트 형태일 수 있음 (각 쿼리마다 결과 리스트)
    if isinstance(results, list) and len(results) > 0:
        if isinstance(results[0], list):
            query_results = results[0]
        else:
            query_results = results
    else:
        query_results = results
    
    if not query_results:
        return
    
    for result in query_results[:limit]:
        # sentence 필드 추출 (여러 가능한 구조 지원)
        sentence = None
        if 'entity' in result and isinstance(result['entity'], dict):
            sentence = result['entity'].get('sentence')
        if not sentence:
            sentence = result.get('sentence')
        
        if sentence:
            print(sentence)
    
if __name__ == "__main__":
    
    result = RAG("주택 임대차가뭐야?", limit=5)
    print_results("주택 임대차가뭐야?", result, limit=5)