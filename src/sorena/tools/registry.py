import json

from sorena.tools import (
    calendar_tool,
    delegation_tool,
    digest_tool,
    file_search_tool,
    interview_tool,
    jobscout_tool,
    quiz_tool,
    recall_tool,
    shell_tool,
    time_tool,
    vault_tool,
    web_search_tool,
)

TOOLS = {
    "get_current_time": time_tool.run,
    "search_files": file_search_tool.run,
    "web_search": web_search_tool.run,
    "run_shell_command": shell_tool.run,
    "recall_memory": recall_tool.run,
    "list_calendar_events": calendar_tool.list_events,
    "create_calendar_event": calendar_tool.create_event,
    "add_quiz_item": quiz_tool.add_quiz_item,
    "get_due_quiz_items": quiz_tool.get_due_quiz_items,
    "record_quiz_result": quiz_tool.record_quiz_result,
    "save_interview_score": interview_tool.save_interview_score,
    "get_interview_history": interview_tool.get_interview_history,
    "ask_researcher": delegation_tool.ask_researcher,
    "notify_coach_of_skill_gap": delegation_tool.notify_coach_of_skill_gap,
    "search_and_score_jobs": jobscout_tool.search_and_score_jobs,
    "get_skill_gap": jobscout_tool.get_skill_gap,
    "get_cv": jobscout_tool.get_cv,
    "get_job_posting": jobscout_tool.get_job_posting,
    "save_job_match_score": jobscout_tool.save_job_match_score,
    "get_job_match_history": jobscout_tool.get_job_match_history,
    "weekly_digest": digest_tool.weekly_digest,
    "write_session_note": vault_tool.write_session_note,
}

TOOL_SCHEMAS = [
    time_tool.SCHEMA,
    file_search_tool.SCHEMA,
    web_search_tool.SCHEMA,
    shell_tool.SCHEMA,
    recall_tool.SCHEMA,
    calendar_tool.LIST_EVENTS_SCHEMA,
    calendar_tool.CREATE_EVENT_SCHEMA,
    quiz_tool.ADD_QUIZ_ITEM_SCHEMA,
    quiz_tool.GET_DUE_QUIZ_ITEMS_SCHEMA,
    quiz_tool.RECORD_QUIZ_RESULT_SCHEMA,
    interview_tool.SAVE_INTERVIEW_SCORE_SCHEMA,
    interview_tool.GET_INTERVIEW_HISTORY_SCHEMA,
    delegation_tool.ASK_RESEARCHER_SCHEMA,
    delegation_tool.NOTIFY_COACH_OF_SKILL_GAP_SCHEMA,
    jobscout_tool.SEARCH_AND_SCORE_JOBS_SCHEMA,
    jobscout_tool.GET_SKILL_GAP_SCHEMA,
    jobscout_tool.GET_CV_SCHEMA,
    jobscout_tool.GET_JOB_POSTING_SCHEMA,
    jobscout_tool.SAVE_JOB_MATCH_SCORE_SCHEMA,
    jobscout_tool.GET_JOB_MATCH_HISTORY_SCHEMA,
    digest_tool.WEEKLY_DIGEST_SCHEMA,
    vault_tool.WRITE_SESSION_NOTE_SCHEMA,
]


class UnknownToolError(Exception):
    pass


class MalformedArgumentsError(Exception):
    pass


def call_tool(name: str, arguments_json: str | None) -> str:
    if name not in TOOLS:
        raise UnknownToolError(f"Unknown tool: {name}")

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        raise MalformedArgumentsError(f"Could not parse arguments for '{name}': {e}") from e

    if not isinstance(args, dict):
        args = {}

    try:
        return TOOLS[name](**args)
    except TypeError as e:
        raise MalformedArgumentsError(f"Invalid arguments for '{name}': {e}") from e


def register_mcp_tools(tools: dict, schemas: list[dict]) -> None:
    TOOLS.update(tools)
    TOOL_SCHEMAS.extend(schemas)
