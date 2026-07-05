"""Quick API test for auto-rename."""
import requests
import time

base = "http://localhost:8000"

# Login
r = requests.post(f"{base}/auth/login", json={"email": "sarah.johnson@student.rhs.edu", "password": "MindBridge2026!"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Create conversation (no title → will be "New Conversation")
r = requests.post(f"{base}/conversations/", json={"title": None}, headers=h)
conv = r.json()
conv_id = conv["conversation_id"]
print(f"Created: id={conv_id}")
print(f"  title='{conv['title']}' ai_gen={conv['ai_generated_title']} msgs={conv['total_messages']}")

# Send message 1
print("\n--- Sending message 1 ---")
r = requests.post(f"{base}/conversations/{conv_id}/messages",
    json={"message_text": "I want to become a pilot when I grow up", "sender_type": "user"}, headers=h)
d = r.json()
print(f"  AI: {d['ai_message']['message_text'][:100]}...")

# Wait to avoid rate limit
print("  (waiting 5s)")
time.sleep(5)

# Send message 2
print("\n--- Sending message 2 ---")
r = requests.post(f"{base}/conversations/{conv_id}/messages",
    json={"message_text": "What subjects should I focus on in school?", "sender_type": "user"}, headers=h)
d = r.json()
print(f"  AI: {d['ai_message']['message_text'][:100]}...")

# Check conversation title
r = requests.get(f"{base}/conversations/{conv_id}", headers=h)
conv = r.json()
print(f"\n--- Result ---")
print(f"  title='{conv['title']}'")
print(f"  ai_generated_title={conv['ai_generated_title']}")
print(f"  total_messages={conv['total_messages']}")

if conv["ai_generated_title"]:
    print("  ✅ AUTO-RENAME WORKS!")
else:
    print("  ❌ AUTO-RENAME FAILED")

# Check memories
r = requests.get(f"{base}/memory/", headers=h)
mems = r.json()
print(f"\n--- Memories: {mems['total']} total ---")
for m in mems["items"][:5]:
    pin = " [PINNED]" if m["is_pinned"] else ""
    print(f"  {m['memory_type']}: {m['content']}{pin}")
