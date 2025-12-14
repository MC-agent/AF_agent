from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymilvus import MilvusClient, DataType, FieldSchema, Collection, connections, CollectionSchema, utility
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client_openai = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPENROUTER_API_KEY"),
)

embedding = OpenAIEmbeddings(
  model="text-embedding-3-small",
) #### embedding 모델 

client = MilvusClient(uri='http://milvus-standalone-name:19530') ### milvus client 

schema = MilvusClient.create_schema(
    auto_id=False,
    enable_dynamic_field=True,
) #### schema 생성


#### schema 생성
schema.add_field(field_name='id',datatype=DataType.INT64,is_primary=True,auto_id=True)
schema.add_field(field_name='sentence',datatype=DataType.VARCHAR,max_length=5000)
schema.add_field(field_name='vector',datatype=DataType.FLOAT_VECTOR,dim=1536)


#### index 생성
index_params = client.prepare_index_params()

index_params.add_index(
  field_name='id',
  index_type='AUTOINDEX'
)

index_params.add_index(
  field_name='vector',
  index_type= 'AUTOINDEX',
  metric_type='COSINE'
)


#### jeonsae라는 collection이 있으면 제거
if client.has_collection("jeonsae"):
    client.drop_collection("jeonsae")
    
#### jeonsae라는 collection이 schema와 index이용해서 생성
client.create_collection(
  collection_name='jeonsae',
  schema=schema,
  index_params=index_params
)


#### 파일 읽기
docs = PyPDFLoader('./주택임대차.pdf').load()

#### 파일 chunk 단위로 나누기 = chunk_size, 겹치는 정도 파악 = chunk_overlap
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000,chunk_overlap=100)

#### 설정한 chunk hyperparameter에 맞게 주택임대차 파일 쪼개기
split_docs = text_splitter.split_documents(docs)

for i in range(len(split_docs)):

  data = []
  try:
    data = []
    
    ## 데이터 넣기 text_splitter를 이용해서 쪼개진 문서는 page_content와 metadata로 나뉘어짐. metadata는 말그대로 페이지 관련된 정보 등이 들어 있음. page_content는 내용
    data.append({"sentence":split_docs[i].page_content,"vector":embedding.embed_documents([split_docs[i].page_content])[0],
            "meta":split_docs[i].metadata})
    
    ## 데이터 넣기
    client.insert("jeonsae",data=data)
  except Exception as e:
    print(f"error : {e}")
    

    
  
