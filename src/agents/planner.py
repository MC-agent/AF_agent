from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter
from typing import Optional
from langchain.tools import tool
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, add_messages
from pydantic import BaseModel
from typing import Annotated, List
from dotenv import load_dotenv
from src.agents.restaurant_agent import load_restaurant_agent
from src.agents.room_check_agent import agent as room_check_agent
from langchain_openai import ChatOpenAI
import os

load_dotenv()
CHATROUTER = os.getenv("OPENROUTER")
BASE_URL = os.getenv("OPENROUTER_API_BASE")


class State(BaseModel):

    messages: Annotated[list, add_messages]


llm = ChatOpenAI(
    api_key=CHATROUTER,
    base_url="https://openrouter.ai/api/v1",
    model="anthropic/claude-sonnet-4.5",
    temperature=0.5
)


restaurant_agent = load_restaurant_agent()



def planner(state:State) -> str:
    planner_prompt_text = """ 너는 계획을 세우는 agent이다. 

    너가 사용하는 agent들은 restaurant_agent와 room_check_agent가 있다.
    그리고너는 사용자의 요구사항을 듣고, restaurant_agent와 room_check_agent를 적절히 활용하여 사용자의 요구사항을 충족시키는 계획을 세워야 한다.

    restaurant_agent는 사용자의 식당 탐색을 돕는 도우미이다. restaurant_info(식당 이름)이라는 도구를 사용할 수 있다. 이 도구는 식당 종류, 식당 이름 또는 위치를 입력받아 해당 식당의 위치, 전화번호, 영업시간 등의 정보를 반환한다.
    room_check_agent는 숙소의 실시간 예약 가능 여부를 확인하는 도우미이다. check_availability(숙소 이름, 체크인 날짜, 체크아웃 날짜, 투숙 인원, 룸 타입)이라는 도구를 사용할 수 있다. 이 도구는 특정 날짜에 예약 가능한 객실이 있는지, 룸 타입별로 몇 개의 객실이 남아있는지 확인한다.

    사용자 입력:
    {messages}
    """

    planner_prompt = ChatPromptTemplate.from_template(planner_prompt_text)

    chain = {"messages": RunnablePassthrough()} | planner_prompt | llm | StrOutputParser()

    response = chain.invoke(state.messages)
    return response


def supervisor(state:State) -> str:
    restaurant_agent = load_restaurant_agent()

    supervisor_agent = create_supervisor(
        [restaurant_agent, room_check_agent],
        model=llm,
    )



    response = supervisor_agent.invoke(state.messages)
    return response


graph_builder = StateGraph(State)
graph_builder.add_node("planner", planner)
graph_builder.add_node("supervisor", supervisor)
graph_builder.add_edge("planner", "supervisor")
graph_builder.set_entry_point("planner")
graph = graph_builder.compile()


if __name__ == '__main__':

    user_input = "홍대에 있는 맛집 알려줘"
    initial_state = State(messages=[user_input])
    response = graph.invoke(initial_state)
    print(response)