from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel
from typing import Annotated, List
from dotenv import load_dotenv
from src.agents.restaurant_agent import load_restaurant_agent
from src.agents.room_agent import agent as room_check_agent
import os
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

memory = InMemorySaver()


load_dotenv()
# os.environ["LANGCHAIN_TRACING_V2"] = 'true'
# os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
# os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
# os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
CHATROUTER = os.getenv("OPENROUTER")
BASE_URL = os.getenv("OPENROUTER_API_BASE")


class State(BaseModel):

    messages: Annotated[List, add_messages] 

llm = ChatOpenAI(
    api_key=CHATROUTER,
    base_url="https://openrouter.ai/api/v1",
    model="anthropic/claude-sonnet-4.5",
    temperature=0.5
)
restaurant_agent = load_restaurant_agent()
supervisor = create_supervisor([restaurant_agent, room_check_agent],model=llm,prompt=(
    "너는 슈퍼바이저 역할을 하는 에이전트야. 너의 역할은 사용자의 요구사항을 듣고, restaurant_agent와 room_check_agent를 적절히 활용하여 사용자의 요구사항을 충족시키는 계획을 세우는 거야."
    "restaurant_agent는 사용자의 식당 탐색을 돕는 도우미야. restaurant_info(식당 이름)이라는 도구를 사용할 수 있어. 이 도구는 식당 종류, 식당 이름 또는 위치를 입력받아 해당 식당의 위치, 전화번호, 영업시간 등의 정보를 반환해줘."
    "room_check_agent는 숙소의 실시간 예약 가능 여부를 확인하는 도우미야. check_availability(숙소 이름, 체크인 날짜, 체크아웃 날짜, 투숙 인원, 룸 타입)이라는 도구를 사용할 수 있어. 이 도구는 특정 날짜에 예약 가능한 객실이 있는지, 룸 타입별로 몇 개의 객실이 남아있는지 확인해줘."))    

def SupervisorAgent(state: State) -> str:
    app = supervisor.compile()
  
    result = app.invoke({
    "messages": [
        {
            "role": "user",
            "content": state.messages[-1]
        }
    ]
    })
    return result['messages'][-1].content

graph_builder = StateGraph(State)
graph_builder.add_node("SupervisorAgent", SupervisorAgent)
graph_builder.set_entry_point("SupervisorAgent")

agent = graph_builder.compile()


if __name__ == "__main__":
    # state = State(messages=["홍대에 있는 중국집 찾아줘"])


    # result = graph_builder.invoke(state)
    result = SupervisorAgent(State(messages=["강남에 있는 숙소 찾아줘"]))
    print(result)