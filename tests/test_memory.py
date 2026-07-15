from sorena.memory import ConversationMemory


def test_add_accumulates_messages_under_budget():
    memory = ConversationMemory(token_budget=1000)
    memory.add({"role": "user", "content": "hi"})
    memory.add({"role": "assistant", "content": "hello"})

    assert len(memory.messages) == 2


def test_compression_creates_system_summary_message(monkeypatch):
    monkeypatch.setattr("sorena.memory.router.chat", lambda messages, **kwargs: "the summary")
    memory = ConversationMemory(token_budget=50)

    for i in range(20):
        memory.add({"role": "user", "content": f"message {i} with padding words to add tokens"})

    assert memory.messages[0]["role"] == "system"
    assert "the summary" in memory.messages[0]["content"]


def test_token_count_stays_bounded_over_long_conversation(monkeypatch):
    monkeypatch.setattr("sorena.memory.router.chat", lambda messages, **kwargs: "short summary")
    memory = ConversationMemory(token_budget=200)

    for i in range(100):
        memory.add({"role": "user", "content": f"padding message number {i} " * 5})

    # unbounded growth over 100 padded messages would be thousands of tokens;
    # compression must have kicked in and kept the tail from scaling with i
    assert memory.token_count() < 500
    assert len(memory.messages) < 100
