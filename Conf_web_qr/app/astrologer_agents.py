import uuid
import logging
from typing import Any, Dict

try:
    from autogen import ConversableAgent, GroupChat, GroupChatManager, UserProxyAgent
except ImportError:  # pragma: no cover - autogen may not be installed in test env
    ConversableAgent = GroupChat = GroupChatManager = UserProxyAgent = None  # type: ignore

logger = logging.getLogger(__name__)

# Basic LLM configuration placeholder
llm_config_openrouter = {"model": "openrouter/auto"}

# Specialist Agents
query_preprocessor_agent = ConversableAgent(
    name="QueryPreprocessorAgent",
    system_message=(
        "You are an expert in Vedic astrology. Your task is to analyze user questions and either approve them, rephrase them, or provide feedback for improvement. Follow these steps:\n"
        "1. First, classify the question into one of three categories: 'Good', 'Needs Reframing', or 'Invalid'.\n"
        "2. If the question is 'Good' (i.e., self-directed and astrological), return the original question followed by 'TERMINATE'.\n"
        "3. If the question 'Needs Reframing' (i.e., not self-directed or not astrological but has potential), rephrase it as a self-directed, astrological question. Return the rephrased question followed by 'TERMINATE'.\n"
        "4. If the question is 'Invalid' (i.e., cannot be answered astrologically), provide a brief, helpful message explaining why and suggest how the user can ask a better question. Return this feedback message followed by 'TERMINATE'.\n"
    ),
    llm_config=llm_config_openrouter,
    human_input_mode="NEVER",
    is_termination_msg=lambda msg: "TERMINATE" in msg["content"],
)


def run_agentic_workflow(query: str, user_data: Dict[str, Any], persona: str) -> str:
    """Orchestrates the multi-agent workflow with improved error handling and logging."""
    workflow_id = str(uuid.uuid4())[:8]
    logger.info(f"[{workflow_id}] Starting workflow for persona {persona}")

    # First classify and potentially rephrase the query
    try:
        logger.debug(f"[{workflow_id}] Preprocessing query")
        classify_chat = GroupChat(agents=[query_preprocessor_agent])
        classifier_manager = GroupChatManager(groupchat=classify_chat, llm_config=llm_config_openrouter)
        classifier_proxy = UserProxyAgent(
            name="ClassifierProxy",
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: True,
        )
        classifier_proxy.initiate_chat(classifier_manager, message=query)
        processed_output = classify_chat.messages[-1]["content"].replace("TERMINATE", "").strip()

        if "sorry" in processed_output.lower() or "cannot answer" in processed_output.lower():
            logger.info(f"[{workflow_id}] Query rejected with feedback: {processed_output}")
            return processed_output  # Return the feedback to the user
        else:
            query = processed_output  # Use the (potentially rephrased) query
            logger.info(f"[{workflow_id}] Query approved/rephrased to: {query}")

    except Exception as e:  # pragma: no cover - safety net
        logger.exception(f"[{workflow_id}] Error during query preprocessing: {e}")
        return "An error occurred while processing your request."

    # Placeholder for main analysis workflow
    logger.debug(f"[{workflow_id}] Proceeding with main analysis")
    return f"Processed query: {query}"
