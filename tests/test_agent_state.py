import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claimguard.agent_runtime.audit import (
    AuditEvent,
    InMemoryAuditSink,
    JsonlAuditSink,
)
from claimguard.agent_runtime.state import ConversationState, InMemorySessionStore


class AgentStateTest(unittest.TestCase):
    def test_session_store_is_scoped_by_tenant_and_session(self):
        store = InMemorySessionStore()
        state = ConversationState(
            tenant_id="tenant-a",
            session_id="session-1",
            user_id="agent-7",
            current_agent="Policy Agent",
            input_items=({"role": "user", "content": "保单等待期是多久？"},),
        )

        store.save(state)

        self.assertEqual(store.load("tenant-a", "session-1"), state)
        self.assertIsNone(store.load("tenant-b", "session-1"))
        self.assertEqual(
            store.load("tenant-a", "session-1").input_items,
            ({"role": "user", "content": "保单等待期是多久？"},),
        )

    def test_session_store_rejects_blank_tenant_or_session_identifiers(self):
        store = InMemorySessionStore()
        valid_state = ConversationState(
            tenant_id="tenant-a",
            session_id="session-1",
            user_id="agent-7",
            current_agent="Policy Agent",
        )

        with self.assertRaisesRegex(ValueError, "tenant_id must be non-empty"):
            store.load(" ", "session-1")
        with self.assertRaisesRegex(ValueError, "session_id must be non-empty"):
            store.load("tenant-a", " ")

        with self.assertRaisesRegex(ValueError, "tenant_id must be non-empty"):
            store.save(
                ConversationState(
                    tenant_id=" ",
                    session_id=valid_state.session_id,
                    user_id=valid_state.user_id,
                    current_agent=valid_state.current_agent,
                )
            )
        with self.assertRaisesRegex(ValueError, "session_id must be non-empty"):
            store.save(
                ConversationState(
                    tenant_id=valid_state.tenant_id,
                    session_id=" ",
                    user_id=valid_state.user_id,
                    current_agent=valid_state.current_agent,
                )
            )

    def test_audit_event_rejects_secret_fields_nested_in_details(self):
        with self.assertRaisesRegex(ValueError, "sensitive audit field"):
            AuditEvent(
                event_type="model_call",
                tenant_id="tenant-a",
                session_id="session-1",
                user_id="agent-7",
                details={"metadata": {"Authorization": "must-not-be-recorded"}},
            )

    def test_audit_event_rejects_raw_customer_message_details(self):
        with self.assertRaisesRegex(ValueError, "raw customer message"):
            AuditEvent(
                event_type="model_call",
                tenant_id="tenant-a",
                session_id="session-1",
                user_id="agent-7",
                details={"customer_message": "我的保单号是 P-12345"},
            )

    def test_audit_event_rejects_raw_message_field_names_at_any_depth(self):
        for field_name in (
            "history",
            "messages",
            "conversation",
            "transcript",
            "input_items",
            "message",
            "content",
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, "raw customer message"):
                    AuditEvent(
                        event_type="model_call",
                        tenant_id="tenant-a",
                        session_id="session-1",
                        user_id="agent-7",
                        details={"metadata": {field_name: "redacted"}},
                    )

    def test_audit_event_rejects_aliased_sdk_message_item(self):
        with self.assertRaisesRegex(ValueError, "raw customer message"):
            AuditEvent(
                event_type="model_call",
                tenant_id="tenant-a",
                session_id="session-1",
                user_id="agent-7",
                details={
                    "metadata": {
                        "previous_turn": {
                            "role": "user",
                            "content": "我的保单号是 P-12345",
                        }
                    }
                },
            )

    def test_in_memory_audit_sink_rejects_mutated_credential_details(self):
        event = AuditEvent(
            event_type="run_completed",
            tenant_id="tenant-a",
            session_id="session-1",
            user_id="agent-7",
            details={"current_agent": "Policy Agent"},
        )
        event.details["metadata"] = {"access_token": "redacted"}
        sink = InMemoryAuditSink()

        with self.assertRaisesRegex(ValueError, "sensitive audit field"):
            sink.record(event)

        self.assertEqual(sink.events, [])

    def test_jsonl_audit_sink_rejects_mutated_credential_details(self):
        event = AuditEvent(
            event_type="run_completed",
            tenant_id="tenant-a",
            session_id="session-1",
            user_id="agent-7",
            details={"current_agent": "Policy Agent"},
        )
        event.details["metadata"] = {"access_token": "redacted"}

        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            sink = JsonlAuditSink(path)

            with self.assertRaisesRegex(ValueError, "sensitive audit field"):
                sink.record(event)

            self.assertFalse(path.exists())

    def test_in_memory_audit_sink_rejects_mutated_aliased_sdk_message_item(self):
        event = AuditEvent(
            event_type="run_completed",
            tenant_id="tenant-a",
            session_id="session-1",
            user_id="agent-7",
            details={"current_agent": "Policy Agent"},
        )
        event.details["metadata"] = {
            "previous_turn": {"role": "user", "content": "我的保单号是 P-12345"}
        }
        sink = InMemoryAuditSink()

        with self.assertRaisesRegex(ValueError, "raw customer message"):
            sink.record(event)

        self.assertEqual(sink.events, [])

    def test_jsonl_audit_sink_rejects_mutated_aliased_sdk_message_item(self):
        event = AuditEvent(
            event_type="run_completed",
            tenant_id="tenant-a",
            session_id="session-1",
            user_id="agent-7",
            details={"current_agent": "Policy Agent"},
        )
        event.details["metadata"] = {
            "previous_turn": {"role": "user", "content": "我的保单号是 P-12345"}
        }

        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            sink = JsonlAuditSink(path)

            with self.assertRaisesRegex(ValueError, "raw customer message"):
                sink.record(event)

            self.assertFalse(path.exists())

    def test_in_memory_audit_sink_assigns_sequential_audit_ids(self):
        sink = InMemoryAuditSink()
        event = AuditEvent(
            event_type="run_completed",
            tenant_id="tenant-a",
            session_id="session-1",
            user_id="agent-7",
            details={"current_agent": "Policy Agent"},
        )

        audit_id = sink.record(event)

        self.assertEqual(audit_id, "audit-000001")
        self.assertEqual(sink.events, [event])

    def test_jsonl_audit_sink_persists_sanitized_event(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            sink = JsonlAuditSink(path)
            audit_id = sink.record(
                AuditEvent(
                    event_type="run_completed",
                    tenant_id="tenant-a",
                    session_id="session-1",
                    user_id="agent-7",
                    details={"current_agent": "Policy Agent"},
                )
            )

            record = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(record["audit_id"], audit_id)
        self.assertRegex(audit_id, r"^audit-[0-9a-f]+$")
        self.assertEqual(record["event_type"], "run_completed")
        self.assertTrue(record["recorded_at"].endswith("+00:00"))
        self.assertNotIn("message", record["details"])


if __name__ == "__main__":
    unittest.main()
