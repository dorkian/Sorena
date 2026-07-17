"""Weekly digest for Scribe (docs/specs/sorena-multi-agent-plan.md §2, §5
step 8): aggregates the last 7 days of quiz accuracy, interview score
trend, and job-match grade distribution into one text summary.

Scope note (resolved during the /build pass for step 8, also recorded in
the spec itself): this covers Scribe's own §2 bullet only -- "what you
learned, quiz scores, interview performance trend" plus job-match counts,
since that data already exists from step 7. The separate JobScout->Scribe
"weekly market report" (trending skills across postings, §2) is NOT part
of this -- unscoped future work, not yet assigned a build step.

No charting library exists in this project and there's no UI surface for
one -- "progress charts" is rendered as a structured text summary, not an
image.

Pure aggregation/formatting: each source module (quiz_tool, interview_tool,
jobscout_tool) owns its own data and query; this module just reads their
raw rows and writes the summary.
"""

from sorena.tools import interview_tool, jobscout_tool, quiz_tool

DIGEST_DAYS = 7

WEEKLY_DIGEST_SCHEMA = {
    "type": "function",
    "function": {
        "name": "weekly_digest",
        "description": (
            "Summarize the last 7 days: quiz accuracy and topics covered, interview score "
            "trend, and job-match grade distribution. Text summary, not a chart image."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def _quiz_section() -> str:
    attempts = quiz_tool.get_recent_quiz_attempts(DIGEST_DAYS)
    if not attempts:
        return "Quiz: no attempts this week."

    total = len(attempts)
    correct = sum(1 for _, is_correct, _ in attempts if is_correct)
    topics = sorted({topic for topic, _, _ in attempts})
    accuracy = round(100 * correct / total)
    return (
        f"Quiz: {correct}/{total} correct ({accuracy}%) across {len(topics)} "
        f"topic(s): {', '.join(topics)}."
    )


def _interview_section() -> str:
    scores = interview_tool.get_recent_interview_scores(DIGEST_DAYS)
    if not scores:
        return "Interview practice: no sessions this week."

    averages = [avg for _, avg in scores]
    overall = sum(averages) / len(averages)
    trend = ""
    if len(averages) >= 2:
        midpoint = len(averages) // 2
        first_half = sum(averages[:midpoint]) / midpoint
        second_half = sum(averages[midpoint:]) / (len(averages) - midpoint)
        if second_half > first_half + 0.2:
            trend = " (improving)"
        elif second_half < first_half - 0.2:
            trend = " (declining)"
        else:
            trend = " (steady)"
    return f"Interview practice: {len(averages)} session(s), avg {overall:.1f}/5{trend}."


def _job_match_section() -> str:
    matches = jobscout_tool.get_recent_job_match_scores(DIGEST_DAYS)
    if not matches:
        return "Job matches: no deep-dive scores this week."

    grade_counts: dict[str, int] = {}
    for _, grade in matches:
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    distribution = ", ".join(f"{count} {grade}" for grade, count in sorted(grade_counts.items()))
    return f"Job matches: {len(matches)} posting(s) scored -- {distribution}."


def weekly_digest() -> str:
    return "\n".join([_quiz_section(), _interview_section(), _job_match_section()])
