from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool

load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = 'true'
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
CHATROUTER = os.getenv("OPENROUTER")
BASE_URL = os.getenv("OPENROUTER_API_BASE")

# LLM 설정
llm = ChatOpenAI(
    api_key=CHATROUTER,
    base_url=BASE_URL,
    model="anthropic/claude-sonnet-4.5",
    temperature=0.5
)

@tool
def translate_tool(text: str) -> str:
    """사용자가 입력한 텍스트 언어를 감지하고, 적절한 언어로 답변을 제공합니다.
    한국어/영어/일본어 입력하면 반드시 같은 언어로 답변합니다."""
    
    prompt = """
    당신은 번역 및 응답 어시스턴트입니다.
    
    사용자가 입력한 텍스트의 언어를 자동으로 감지하고, 
    반드시 다음 규칙에 따라 답변해야 합니다:
    
    - 한국어로 질문하면 반드시 한국어로 답변해 
    - 영어로 질문하면 반드시 영어로 답변해
    - 일본어로 질문하면 반드시 일본어로 답변해
    
    입력된 텍스트의 질문에 대해 친절하고 상세하고 귀엽게 이모티콘을 사용해서 답변해
    
    사용자 입력: {text}
    """
    
    prompt_template = ChatPromptTemplate.from_template(prompt)
    chain = prompt_template | llm | StrOutputParser()
    response = chain.invoke({"text": text})
    return response


# Agent 생성
agent = create_react_agent(
    model=llm,
    tools=[translate_tool],
    prompt="당신은 translate_tool만 사용할 수 있습니다.",
)

if __name__ == "__main__":
    result = agent.invoke({"messages": [{"role": "user", "content": "大阪のゆうめなところを探してみて！"}]})
    print(result['messages'][-1].content)
