"""Force the primary provider to fail and show the router falling back automatically."""

from sorena import router

router.PROVIDER_CHAIN[0] = "groq/not-a-real-model"

reply = router.chat([{"role": "user", "content": "Say hi in exactly 5 words"}])
print(f"\nFinal reply: {reply}")
