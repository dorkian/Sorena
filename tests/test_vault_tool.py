from sorena.tools import vault_tool


def test_write_session_note_creates_file_with_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT_SESSIONS_PATH", tmp_path)

    result = vault_tool.write_session_note(
        title="Weekly Digest", content="Quiz: 2/3 correct.", slug="weekly-digest"
    )

    assert "Saved note to vault" in result
    files = list(tmp_path.glob("*-weekly-digest.md"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "type: session" in text
    assert "project: sorena-ai-assistant" in text
    assert "# Weekly Digest" in text
    assert "Quiz: 2/3 correct." in text


def test_write_session_note_derives_slug_from_title_when_omitted(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT_SESSIONS_PATH", tmp_path)

    vault_tool.write_session_note(title="Today's Learning Session!", content="notes")

    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1
    assert "todays-learning-session" in files[0].name


def test_write_session_note_never_overwrites_same_day_same_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT_SESSIONS_PATH", tmp_path)

    vault_tool.write_session_note(title="Note One", content="first", slug="daily")
    vault_tool.write_session_note(title="Note Two", content="second", slug="daily")

    files = list(tmp_path.glob("*daily*.md"))
    assert len(files) == 2
    contents = [f.read_text() for f in files]
    assert any("first" in c for c in contents)
    assert any("second" in c for c in contents)


def test_write_session_note_collision_uses_disambiguated_slug_everywhere(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT_SESSIONS_PATH", tmp_path)
    index = tmp_path / "INDEX.md"
    index.write_text("---\ntype: index\n---\n\n| Date | Session | Summary |\n|---|---|---|\n")

    vault_tool.write_session_note(title="Weekly Digest", content="first", slug="weekly-digest")
    vault_tool.write_session_note(title="Weekly Digest", content="second", slug="weekly-digest")

    second_file = next(tmp_path.glob("*weekly-digest-2.md"))
    assert "slug: weekly-digest-2" in second_file.read_text()

    index_lines = index.read_text().splitlines()
    assert any("[weekly-digest]" in line for line in index_lines)
    assert any("[weekly-digest-2]" in line for line in index_lines)


def test_write_session_note_appends_to_existing_index(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT_SESSIONS_PATH", tmp_path)
    index = tmp_path / "INDEX.md"
    index.write_text("---\ntype: index\n---\n\n| Date | Session | Summary |\n|---|---|---|\n")

    vault_tool.write_session_note(title="New Entry", content="body", slug="new-entry")

    index_text = index.read_text()
    assert "new-entry" in index_text
    assert "New Entry" in index_text


def test_write_session_note_skips_index_update_when_index_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT_SESSIONS_PATH", tmp_path)

    result = vault_tool.write_session_note(title="No Index Here", content="body")

    # doesn't crash just because INDEX.md doesn't exist in this vault
    assert "Saved note to vault" in result
    assert not (tmp_path / "INDEX.md").exists()


def test_write_session_note_missing_vault_folder_reports_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_tool, "VAULT_SESSIONS_PATH", tmp_path / "does_not_exist")

    result = vault_tool.write_session_note(title="X", content="Y")

    assert "not found" in result
    assert "couldn't save" in result


def test_slugify_handles_punctuation_and_case():
    assert vault_tool._slugify("Today's Learning Session!") == "todays-learning-session"
    assert vault_tool._slugify("") == "note"
    assert vault_tool._slugify("   ") == "note"
