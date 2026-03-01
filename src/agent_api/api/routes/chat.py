import structlog
from fastapi import APIRouter, Depends

from agent_api.agent.engine import AgentEngine
from agent_api.api.dependencies import get_agent_engine
from agent_api.models.schemas import ChatRequest, ChatResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["AI Agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest, engine: AgentEngine = Depends(get_agent_engine)
) -> ChatResponse:
    """
    Submits a natural language prompt to the Autonomous E-Commerce Agent.
    """

    # The engine orchestrates the entire Reason -> Act -> Observe loop autonomously
    final_answer = await engine.run(user_prompt=request.prompt, user_id=request.user_id)

    return ChatResponse(response=final_answer)
