# MindBridge API Reference

> Base URL: `http://localhost:8000`
> Authentication: Bearer JWT in `Authorization` header

---

## 🔐 Authentication

### POST `/auth/signup`
Register a new user account.

**Request Body:**
```json
{
  "email": "user@school.edu",
  "password": "SecurePass123!",
  "first_name": "Jane",
  "last_name": "Doe",
  "role": "student",
  "school_code": "RHS2026"
}
```

**Response (201):**
```json
{
  "tokens": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 1800
  },
  "user": {
    "user_id": "uuid",
    "email": "user@school.edu",
    "role": "student",
    "first_name": "Jane",
    "last_name": "Doe"
  }
}
```

### POST `/auth/login`
Authenticate with email and password.

### POST `/auth/refresh`
Refresh an expired access token.

### GET `/auth/me`
Get the authenticated user's profile.

---

## 👤 Users

### GET `/users/me`
Get full profile with role-specific data.

### PUT `/users/me`
Update profile fields (first_name, last_name, phone, profile_image).

### GET `/users/{user_id}`
Get a user by ID. *Admin/School Admin/Counselor only.*

### GET `/users/`
List users in tenant. *Admin/School Admin only.*

---

## 💬 Conversations

### POST `/conversations/`
Create a new conversation.

### GET `/conversations/`
List conversations (paginated, newest first).

**Query Params:** `page`, `page_size`, `include_archived`

### GET `/conversations/{id}`
Get conversation with all messages.

### PUT `/conversations/{id}`
Update title or archive status.

### DELETE `/conversations/{id}`
Soft-delete (archive) a conversation.

### POST `/conversations/{id}/messages`
Send a message.

**Request Body:**
```json
{
  "message_text": "I'm feeling stressed about exams.",
  "sender_type": "user"
}
```

### GET `/conversations/{id}/messages`
Get messages with cursor-based pagination.

**Query Params:** `cursor` (message_id), `limit`

---

## 🧠 Memory

### POST `/memory/`
Store a new memory item.

### GET `/memory/`
List memory items. **Query:** `memory_type`

### DELETE `/memory/{id}`
Delete a memory item.

---

## 💚 Wellness

### POST `/wellness/records`
Log daily wellness check-in (mood, stress, confidence, anxiety, energy: 1-10).

### GET `/wellness/records`
Get wellness history. **Query:** `start_date`, `end_date`

### POST `/wellness/goals`
Create a goal.

### GET `/wellness/goals`
List goals. **Query:** `status`

### PUT `/wellness/goals/{id}`
Update goal status/details.

### POST `/wellness/journal`
Create a journal entry.

### GET `/wellness/journal`
List journal entries (paginated).

---

## ⚠️ Risk Detection

### POST `/risk/assessments`
Create risk assessment. *Counselor/Admin only.*

### GET `/risk/assessments/{student_id}`
List assessments for a student.

### GET `/risk/alerts`
Get active high-risk alerts for the tenant.

---

## 👨‍👩‍👧 Parents

### GET `/parents/children`
List linked children with wellness summaries.

### GET `/parents/children/{student_id}/insights`
Get aggregated insights (wellness trend, recommendations). *Never exposes raw conversations.*

---

## 🩺 Counselors

### GET `/counselors/students`
List students in tenant with risk profiles.

### POST `/counselors/sessions`
Schedule a session.

### GET `/counselors/sessions`
List sessions. **Query:** `status`

### PUT `/counselors/sessions/{id}`
Update session status.

### POST `/counselors/sessions/{id}/notes`
Add a session note.

### GET `/counselors/sessions/{id}/notes`
Get session notes.

---

## 📊 Analytics

### GET `/analytics/overview`
School-wide metrics (students, wellness, risk distribution). *School Admin only.*

### GET `/analytics/snapshots`
Historical monthly snapshots.

---

## 🔔 Notifications

### GET `/notifications/`
List notifications with unread count.

### PUT `/notifications/{id}/read`
Mark notification as read.

### PUT `/notifications/read-all`
Mark all as read.

---

## 💳 Subscriptions

### GET `/subscriptions/current`
Get active subscription.

### GET `/subscriptions/transactions`
List payment history.

---

## ⚙️ Admin

### GET `/admin/tenants`
List all tenants. *Platform Admin only.*

### POST `/admin/tenants`
Create a new tenant.

### PUT `/admin/tenants/{id}`
Update tenant.

### GET `/admin/prompts`
List AI prompt versions.

### POST `/admin/prompts`
Create AI prompt.

### GET `/admin/audit-logs`
View audit trail.

---

## 🏥 Health

### GET `/health`
Basic health check.

### GET `/health/db`
Database connectivity check.
