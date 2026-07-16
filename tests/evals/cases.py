"""Eval cases for Sorena's agent loop -- see docs/specs/phase-6-evals-observability.md
and docs/adr/0010-eval-suite-scripted-plus-live-tiers.md.

Two tiers, run by the same harness in test_evals.py:

- Deterministic (live=False): the LLM's decision at each hop is scripted
  (see harness.py). These test the agent loop's orchestration mechanics --
  correct dispatch, error recovery, trace capture, exception handling --
  without a real API call, so they're CI-gated and can never flake. Most
  are regression cases mined from real bugs hit in Phases 2, 3, and 5.

- Live (live=True): a real LLM call via router.chat(), using whichever
  provider is configured in .env. These test genuine tool-selection
  judgment -- something a scripted decision cannot evaluate, since the
  case itself would be scripting the answer it's supposedly checking.
  Skipped automatically when no provider API key is configured (e.g. in
  CI, which has none) -- see test_evals.py's _has_real_api_key().

To add a new case: append an EvalCase to ALL_CASES. Deterministic cases
need a `script` (see harness.py's tool_call/tool_calls/final helpers).
Live cases just need a `user_message` and what to check for.
"""

from dataclasses import dataclass, field

from sorena.agent import MaxHopsExceededError

from .harness import final, tool_call, tool_calls


@dataclass
class EvalCase:
    name: str
    case_type: str  # "regression" | "tool_selection" | "orchestration"
    user_message: str
    script: list | None = None
    live: bool = False
    expect_tool_called: str | list[str] | None = None
    expect_no_tool_called: bool = False
    expect_answer_contains: str | None = None
    expect_exception: type | None = None
    expect_step_result_contains: str | None = None
    expect_step_succeeds: bool = False
    seed_long_term: list[tuple[str, str, str]] = field(default_factory=list)
    mock_web_search: str | None = None


DETERMINISTIC_CASES = [
    # --- regressions: real bugs hit in earlier phases ------------------------
    EvalCase(
        name="unknown_tool_recovers_gracefully",
        case_type="regression",
        user_message="call a tool that doesn't exist",
        script=[tool_call("not_a_real_tool"), final("Sorry, I can't do that.")],
        expect_answer_contains="sorry",
    ),
    EvalCase(
        name="malformed_json_args_recovers_gracefully",
        case_type="regression",
        user_message="call a tool with broken arguments",
        script=[tool_call("get_current_time", arguments="{not valid json"), final("Noted.")],
        expect_answer_contains="noted",
    ),
    EvalCase(
        name="null_string_args_does_not_crash",
        case_type="regression",
        user_message="what time is it",
        # some providers send the literal JSON string "null" for a no-arg
        # tool call -- json.loads("null") == None, which used to crash as
        # **None before this was fixed in the tool registry
        script=[tool_call("get_current_time", arguments="null"), final("It's now.")],
        expect_tool_called="get_current_time",
        expect_answer_contains="now",
        # the tool must actually SUCCEED, not just get attempted -- without
        # this, a regression that turns the call into a caught, swallowed
        # error would still pass, since the scripted final answer doesn't
        # depend on the real tool result
        expect_step_succeeds=True,
    ),
    EvalCase(
        name="empty_string_args_defaults_cleanly",
        case_type="regression",
        user_message="what time is it",
        script=[tool_call("get_current_time", arguments=""), final("It's now.")],
        expect_tool_called="get_current_time",
    ),
    EvalCase(
        name="rrf_bare_number_regression",
        case_type="regression",
        user_message="what did I say about the Docker error",
        script=[
            tool_call("recall_memory", arguments='{"query": "137"}'),
            final("It was a Docker OOM error."),
        ],
        seed_long_term=[
            ("user", "Docker build is failing with exit code 137, probably OOM killed.", "t1"),
            ("user", "PIN for the storage locker is 7734.", "t2"),
        ],
        expect_tool_called="recall_memory",
        # a bare-number query barely moves a semantic embedding, so
        # vector-only search picks the wrong (PIN) turn -- FTS5's exact-
        # token match is what rescues the right one once fused in. This
        # case regresses the RRF candidate-pool bug fixed during Phase 5.
        expect_step_result_contains="Docker",
    ),
    EvalCase(
        name="mcp_tool_dispatches_through_same_registry",
        case_type="regression",
        user_message="ping the test MCP server",
        script=[tool_call("mcp_test_server_ping"), final("pong received.")],
        expect_tool_called="mcp_test_server_ping",
        expect_answer_contains="pong",
    ),
    EvalCase(
        name="max_hops_guard_raises_after_exhausting_hops",
        case_type="regression",
        user_message="loop forever",
        script=[tool_call("get_current_time")] * 8,
        expect_exception=MaxHopsExceededError,
    ),
    # --- orchestration: does the loop dispatch/record correctly -------------
    EvalCase(
        name="time_question_calls_time_tool",
        case_type="orchestration",
        user_message="what time is it",
        script=[tool_call("get_current_time"), final("It's noon.")],
        expect_tool_called="get_current_time",
        expect_answer_contains="noon",
    ),
    EvalCase(
        name="file_search_question_calls_search_files_tool",
        case_type="orchestration",
        user_message="find python files in this project",
        script=[
            tool_call("search_files", arguments='{"pattern": "**/*.py"}'),
            final("Found some."),
        ],
        expect_tool_called="search_files",
    ),
    EvalCase(
        name="web_search_question_calls_web_search_tool",
        case_type="orchestration",
        user_message="search the web for the latest AI news",
        script=[
            tool_call("web_search", arguments='{"query": "latest AI news"}'),
            final("Here's what I found."),
        ],
        expect_tool_called="web_search",
        mock_web_search="AI News: things happened.",
    ),
    EvalCase(
        name="recall_question_calls_recall_memory_tool",
        case_type="orchestration",
        user_message="what did I ask you about my passport",
        script=[
            tool_call("recall_memory", arguments='{"query": "passport"}'),
            final("You asked about your passport."),
        ],
        seed_long_term=[
            ("user", "I need to renew my passport before my trip to Japan.", "t1"),
        ],
        expect_tool_called="recall_memory",
        expect_step_result_contains="passport",
    ),
    EvalCase(
        name="direct_answer_no_tool_needed",
        case_type="orchestration",
        user_message="what is 2 plus 2",
        script=[final("2 plus 2 is 4.")],
        expect_no_tool_called=True,
        expect_answer_contains="4",
    ),
    EvalCase(
        name="multi_hop_two_tool_calls_in_one_response",
        case_type="orchestration",
        user_message="what time is it and search the web for the Super Bowl winner",
        script=[
            tool_calls(
                ("get_current_time", "{}"),
                ("web_search", '{"query": "most recent Super Bowl winner"}'),
            ),
            final("It's noon, and the Chiefs won."),
        ],
        expect_tool_called=["get_current_time", "web_search"],
        mock_web_search="The Kansas City Chiefs won the most recent Super Bowl.",
    ),
    EvalCase(
        name="trace_step_captures_real_tool_output",
        case_type="orchestration",
        user_message="what time is it",
        # only the model's *decision* is scripted -- the tool itself
        # executes for real, so this proves the trace records genuine
        # tool output, not just the scripted decision
        script=[tool_call("get_current_time"), final("Noted.")],
        expect_tool_called="get_current_time",
        expect_step_succeeds=True,
    ),
]

LIVE_CASES = [
    EvalCase(
        name="live_time_question_selects_time_tool",
        case_type="tool_selection",
        user_message="What is the current UTC time? Use the tool.",
        live=True,
        expect_tool_called="get_current_time",
    ),
    EvalCase(
        name="live_web_search_question_selects_web_search_tool",
        case_type="tool_selection",
        user_message="Search the web for who won the most recent Super Bowl.",
        live=True,
        expect_tool_called="web_search",
    ),
    EvalCase(
        name="live_file_search_question_selects_search_files_tool",
        case_type="tool_selection",
        user_message="Find all Python files in this project using the file search tool.",
        live=True,
        expect_tool_called="search_files",
    ),
    EvalCase(
        name="live_recall_question_selects_recall_memory_tool_and_answers_correctly",
        case_type="tool_selection",
        user_message="What did I ask you about my passport last week?",
        live=True,
        seed_long_term=[
            ("user", "I need to renew my passport before my trip to Japan in September.", "t1"),
        ],
        expect_tool_called="recall_memory",
        expect_answer_contains="passport",
    ),
    EvalCase(
        name="live_recall_exact_term_query_end_to_end",
        case_type="tool_selection",
        user_message="What did I say about the number 137?",
        live=True,
        seed_long_term=[
            ("user", "Docker build is failing with exit code 137, probably OOM killed.", "t1"),
            ("user", "PIN for the storage locker is 7734.", "t2"),
        ],
        expect_tool_called="recall_memory",
    ),
    EvalCase(
        name="live_simple_math_answers_directly_no_tool",
        case_type="tool_selection",
        user_message="What is 12 plus 30? Just answer, no need to use any tool.",
        live=True,
        expect_no_tool_called=True,
        expect_answer_contains="42",
    ),
    EvalCase(
        name="live_greeting_answers_directly_no_tool",
        case_type="tool_selection",
        user_message="Say hello to me.",
        live=True,
        expect_no_tool_called=True,
    ),
    EvalCase(
        name="live_multi_step_time_and_web_search",
        case_type="tool_selection",
        user_message=(
            "What is the current UTC time, and search the web for who won the most "
            "recent Super Bowl? Use tools for both."
        ),
        live=True,
        expect_tool_called=["get_current_time", "web_search"],
    ),
    EvalCase(
        name="live_recipe_question_does_not_use_shell_tool",
        case_type="tool_selection",
        user_message="What's a good recipe for pancakes?",
        live=True,
        expect_no_tool_called=True,
    ),
]

ALL_CASES = DETERMINISTIC_CASES + LIVE_CASES
