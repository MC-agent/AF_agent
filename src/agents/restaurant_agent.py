from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter
from typing import Optional
from src.memory.vector_store import search_place_embeddings
from dotenv import load_dotenv
from openai import OpenAI
import os
import psycopg2
from sqlalchemy import create_engine, text

from src.config import settings

load_dotenv()
# os.environ["LANGCHAIN_TRACING_V2"] = 'true'
# os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
# os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
# os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
CHATROUTER = os.getenv("OPENROUTER")
BASE_URL = os.getenv("OPENROUTER_API_BASE")



# LLM 설정
llm = ChatOpenAI(
    api_key=CHATROUTER,
    base_url="https://openrouter.ai/api/v1",
    model="anthropic/claude-sonnet-4.5",
    temperature=0.5
)


client = OpenAI( base_url="https://openrouter.ai/api/v1",api_key=CHATROUTER)

engine = create_engine(os.getenv("PGVECTOR_DATABASE_URL"))

@tool
def restaurant_info(restaurant_name: str) -> str:
    """식당의 정보를 제공합니다. 식당 종류, 식당 이름 또는 위치를 입력받아 해당 식당의 위치, 전화번호, 영업시간 등의 정보를 반환합니다."""
    response = client.embeddings.create(
            input=restaurant_name,
            model=settings.embedding_model,
        )
  
    search_results = search_place_embeddings(response, limit=3)

    return search_results


def load_restaurant_agent():
    prompt_text = """
    당신은 사용자의 식당 탐색을 돕는 도우미입니다.
    당신이 사용할 수 있는 도구는 restaurant_info(식당 이름)입니다. 이 도구는 식당 종류, 식당 이름 또는 위치를  해당 식당의 위치, 전화번호, 영업시간 등의 정보를 반환합니다.
    규칙:
    - 사용자의 입력에서 지역, 음식 종류, 식당 이름을 파악하세요.
    - 식당 이름이 명확하면 해당 식당 정보를 찾으세요.
    - 식당 이름이 없고 지역/종류만 있으면 그 조건에 맞는 식당 후보를 찾으세요.
    - 데이터베이스 검색 결과가 없으면 지어내지 말고 없다고 답하세요.
    - 답변은 짧고 명확하게 정리하세요.ㄴ
    """
    agent = create_agent(
    model=llm,
    tools=[restaurant_info],
    system_prompt = prompt_text
    )    

    return agent


if __name__ == '__main__':
    user_input = "홍대에 있는 맛집 알려줘"

    response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    #response = restaurant_info(user_input)

    print(response)