"""Always-on assistant: the face bridge (text chat + orb state, port 8765)
and the hands-free voice loop in one process, so "hey Jarvis" and the web
composer work at the same time. Launched by start.bat.
"""

from sorena import face


def main() -> None:
    # Start the bridge before the heavy voice/agent imports (sentence-transformers,
    # torch, faster-whisper) so the UI connects immediately instead of sitting on
    # "reconnecting..." through the cold-load.
    face.start()
    print("Sorena is up -- face bridge on ws://localhost:8765, loading voice pipeline...")
    from sorena.voice.pipeline import run_voice_turn

    print("Listening for 'hey Jarvis'.")
    while True:
        try:
            run_voice_turn()
        except KeyboardInterrupt:
            print("\nSorena stopped.")
            return
        except Exception as exc:  # one bad turn must not take the face bridge down with it
            print(f"Voice turn failed, still listening: {exc}")


if __name__ == "__main__":
    main()
