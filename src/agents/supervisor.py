from langgraph_supervisor import create_supervisor
from langgraph.graph import add_messages
from pydantic import BaseModel
from typing import Annotated, List, Optional
from dotenv import load_dotenv
from src.agents.restaurant_agent import load_restaurant_agent
from src.agents.room_agent import agent as room_agent
from src.config import settings
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

memory = InMemorySaver()


load_dotenv()


class State(BaseModel):

    messages: Annotated[List, add_messages] 

llm = ChatOpenAI(
    api_key=settings.openrouter,
    base_url=settings.openrouter_api_base,
    model=settings.rag_model,
    temperature=0.5
)
restaurant_agent = load_restaurant_agent()
supervisor = create_supervisor([restaurant_agent, room_agent],model=llm,prompt=(
    "너는 슈퍼바이저 역할을 하는 에이전트야. 사용자의 요청을 읽고 restaurant_agent와 room_check_agent 중 가장 알맞은 에이전트에게 바로 위임해."
    "식당, 맛집, 음식 종류, 식당 이름, 지역 기반 음식점 추천/검색 요청은 restaurant_agent에게 위임해. restaurant_agent는 pgvector에 저장된 카카오맵 식당 데이터를 검색해서 이름, 위치, 전화번호, 영업시간, 평점 등을 반환할 수 있어."
    "숙소, 호텔, 게스트하우스, 리조트, 객실, 예약 가능 여부, 숙소 위치/상세 정보 요청은 room_check_agent에게 위임해. room_check_agent는 pgvector 숙소 검색과 도구를 사용할 수 있어."
    "요청이 식당과 숙소를 모두 포함하면 두 에이전트를 모두 사용해. 검색 결과가 적어도 임의로 없다고 단정하지 말고, 에이전트가 반환한 후보를 사용자에게 요약해."
))

agent = supervisor.compile(checkpointer=memory)


def _thread_config(thread_id: Optional[str]) -> dict:
    return {"configurable": {"thread_id": thread_id or "default"}}


def run_supervisor(user_query: str, thread_id: Optional[str] = None) -> str:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_query}]},
        config=_thread_config(thread_id),
    )
    return result['messages'][-1].content


def SupervisorAgent(state: State, thread_id: Optional[str] = None) -> str:
    last_message = state.messages[-1]
    content = getattr(last_message, "content", last_message)
    return run_supervisor(str(content), thread_id=thread_id or "legacy-supervisor")


if __name__ == "__main__":
    result = run_supervisor("강남에 있는 숙소 추천해줘", thread_id="manual-test")
    print(result)
