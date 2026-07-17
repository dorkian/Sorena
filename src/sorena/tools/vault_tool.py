"""Obsidian vault writer for Scribe (docs/specs/sorena-multi-agent-plan.md
§2, "Every session ends with a structured note to your Obsidian vault...
port [the session-wrap] pattern"): writes session notes to the existing
sorena-ai-assistant project vault folder, following its established
sessions/YYYY-MM-DD-{slug}.md + INDEX.md convention (see vault/RESOLVER.md:
"work on a specific project" -> 01-Projects/{ProjectName}/sessions/) rather
than inventing a new location or format.
"""

import os
import re
from datetime import UTC, datetime
from pathlib import Path

VAULT_SESSIONS_PATH = Path(
    os.getenv(
        "SORENA_VAULT_SESSIONS_PATH",
        "D:/claude-projects/vault/01-Projects/sorena-ai-assistant/sessions",
    )
)

_APOSTROPHE_RE = re.compile(r"['’]")  # straight and curly -- stripped, not treated as a word break
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    # Contractions ("Ash's", "today's") are common in LLM-generated titles --
    # strip the apostrophe first so "today's" becomes "todays", not the
    # uglier "today-s" that treating it as a generic separator would produce.
    without_apostrophes = _APOSTROPHE_RE.sub("", text.lower())
    slug = _SLUG_RE.sub("-", without_apostrophes).strip("-")
    return slug or "note"


WRITE_SESSION_NOTE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_session_note",
        "description": (
            "Save a structured session note (e.g. a session summary or the weekly digest) "
            "to Ash's Obsidian vault. Also updates the vault's session index."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short human-readable title."},
                "content": {"type": "string", "description": "The note body, in markdown."},
                "slug": {
                    "type": "string",
                    "description": (
                        "Short kebab-case slug for the filename, e.g. 'weekly-digest'. "
                        "Derived from the title if omitted."
                    ),
                },
            },
            "required": ["title", "content"],
        },
    },
}


def write_session_note(title: str, content: str, slug: str = "") -> str:
    if not VAULT_SESSIONS_PATH.exists():
        return f"Vault sessions folder not found at {VAULT_SESSIONS_PATH} -- couldn't save."

    base_slug = _slugify(slug or title)
    date = datetime.now(UTC).date().isoformat()

    # effective_slug may gain a -2, -3, ... suffix below on collision -- it's
    # what actually goes in the frontmatter and the index, not base_slug,
    # so two same-day notes never show identical slugs anywhere.
    effective_slug = base_slug
    filename = f"{date}-{effective_slug}.md"
    path = VAULT_SESSIONS_PATH / filename
    counter = 2
    while path.exists():
        # never overwrite an existing note -- another one from today with
        # the same slug gets -2, -3, etc. instead of clobbering it.
        effective_slug = f"{base_slug}-{counter}"
        filename = f"{date}-{effective_slug}.md"
        path = VAULT_SESSIONS_PATH / filename
        counter += 1

    note = (
        "---\n"
        "type: session\n"
        "project: sorena-ai-assistant\n"
        f"date: {date}\n"
        f"slug: {effective_slug}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{content}\n"
    )
    path.write_text(note, encoding="utf-8")
    _append_to_index(date, filename, effective_slug, title)

    return f"Saved note to vault: {filename}"


def _append_to_index(date: str, filename: str, slug: str, title: str) -> None:
    index_path = VAULT_SESSIONS_PATH / "INDEX.md"
    if not index_path.exists():
        return  # don't invent the index file's format if it doesn't already exist
    # link text is the bare slug, matching every existing row (e.g.
    # "[face-ui](...)") -- the date already has its own column, repeating
    # it in the link text (as the full date-slug filename stem) is noise.
    row = f"| {date} | [{slug}]({filename}) | {title} |\n"
    with index_path.open("a", encoding="utf-8") as f:
        f.write(row)
