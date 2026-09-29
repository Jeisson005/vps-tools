import os
import sys
import asyncio

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.clickup import ClickUpService
from src.services.clickup.client import ClickUpClient


def _fake_service() -> ClickUpService:
    return ClickUpService(
        config={}, secrets={},
        instances=[{
            "instance_id": "test",
            "enabled": True,
            "is_default": True,
            "config": {},
            "secrets": {"api_token": "pk_test_token"},
        }],
    )


def test_clickup_comments_client_crud():
    async def run():
        calls = []

        async def fake_request(method, path, *, params=None, json_body=None):
            calls.append({"method": method, "path": path, "params": params, "json_body": json_body})
            if method == "GET":
                return {
                    "comments": [
                        {"id": "c1", "comment_text": "hola", "user": {"username": "jeisson"}, "date": "1",
                         "resolved": False, "assignee": {"id": 42, "username": "jeisson"}, "reply_count": 2},
                    ],
                    "last_page": True,
                }
            if method == "POST":
                return {"id": "c2", "comment_text": "nuevo", "date": "2"}
            if method == "PUT":
                return {"id": "c1", "comment_text": "editado", "date": "1", "resolved": True}
            return {}

        client = ClickUpClient(api_token="pk_test")
        client._request = fake_request  # type: ignore[method-assign]

        listed = await client.list_task_comments(task_id="t1", start=25, start_id="c0")
        assert calls[-1]["method"] == "GET" and calls[-1]["path"] == "/task/t1/comment"
        assert calls[-1]["params"] == {"start": 25, "start_id": "c0"}
        assert listed["count"] == 1 and "next_page" not in listed
        assert listed["comments"][0]["assignee"] == {"id": 42, "username": "jeisson"}
        assert listed["comments"][0]["reply_count"] == 2

        created = await client.create_task_comment(task_id="t1", comment_text="nuevo", assignee=42)
        post_call = [c for c in calls if c["method"] == "POST"][-1]
        assert post_call["path"] == "/task/t1/comment"
        assert post_call["json_body"]["assignee"] == 42
        assert created["id"] == "c2"

        updated = await client.update_task_comment(comment_id="c1", comment_text="editado", resolved=True)
        assert calls[-1]["method"] == "PUT" and calls[-1]["path"] == "/comment/c1"
        assert calls[-1]["json_body"] == {"comment_text": "editado", "resolved": True}
        assert updated["resolved"] is True

        deleted = await client.delete_task_comment(comment_id="c1")
        assert calls[-1]["method"] == "DELETE" and calls[-1]["path"] == "/comment/c1"
        assert deleted == {"id": "c1", "status": "deleted"}

        for coro in (client.update_task_comment(comment_id=""),
                     client.delete_task_comment(comment_id=""),
                     client.list_task_comments(task_id="t1", start=25)):
            try:
                await coro
                raise AssertionError("expected ValueError")
            except ValueError:
                pass

    asyncio.run(run())
    print("[PASS] ClickUp comments client CRUD OK")


def test_clickup_comments_tools_and_dispatch():
    async def run():
        svc = _fake_service()
        names = [t["name"] for t in svc.get_tools()]
        for name in ("clickup_list_task_comments", "clickup_create_task_comment",
                     "clickup_update_task_comment", "clickup_delete_task_comment"):
            assert name in names, f"missing tool {name}"

        client = svc.accounts["test"]

        async def fake_request(method, path, *, params=None, json_body=None):
            if method == "POST":
                return {"id": "c9", "comment_text": json_body.get("comment_text", ""),
                        "assignee": {"id": json_body.get("assignee"), "username": "u"} if json_body.get("assignee") else None}
            if method == "PUT":
                return {"id": "c9", "comment_text": json_body.get("comment_text", "c9"),
                        "resolved": json_body.get("resolved", False)}
            return {"comments": []}

        client._request = fake_request  # type: ignore[method-assign]

        created = await svc.call_tool("clickup_create_task_comment",
                                      {"task_id": "t1", "comment_text": "x", "assignee": 7})
        assert created["id"] == "c9" and created["assignee"] == {"id": 7, "username": "u"}

        updated = await svc.call_tool("clickup_update_task_comment",
                                      {"comment_id": "c9", "resolved": True})
        assert updated["resolved"] is True

        deleted = await svc.call_tool("clickup_delete_task_comment", {"comment_id": "c9"})
        assert deleted["status"] == "deleted"

        listed = await svc.call_tool("clickup_list_task_comments", {"task_id": "t1"})
        assert listed["comments"] == []

    asyncio.run(run())
    print("[PASS] ClickUp comments tools catalog & dispatch OK")


def test_clickup_comment_refetch_and_ack():
    async def run():
        stored = []

        async def fake_request(method, path, *, params=None, json_body=None):
            if method == "POST":
                stored.append({"id": "c10", "comment_text": json_body["comment_text"],
                               "user": {"username": "jeisson"}, "date": "1", "resolved": False,
                               "assignee": {"id": 7, "username": "jeisson"}})
                return {"id": "c10", "hist_id": "h", "date": "1", "version": {}}
            if method == "PUT":
                return {}
            if method == "GET":
                return {"comments": list(stored), "last_page": True}
            return {}

        client = ClickUpClient(api_token="pk_test")
        client._request = fake_request  # type: ignore[method-assign]

        # POST mínimo -> se relee y devuelve el comentario real (texto + assignee)
        created = await client.create_task_comment(task_id="t1", comment_text="hola", assignee=7)
        assert created["comment_text"] == "hola"
        assert created["assignee"] == {"id": 7, "username": "jeisson"}

        # PUT {} sin task_id -> acuse honesto
        ack = await client.update_task_comment(comment_id="c10", resolved=True)
        assert ack == {"id": "c10", "status": "updated", "updated_fields": {"resolved": True}}

        # PUT {} con task_id -> estado real releído
        stored[0]["resolved"] = True
        real = await client.update_task_comment(comment_id="c10", resolved=True, task_id="t1")
        assert real["resolved"] is True and "note" not in real

        # 'resolved' pedido pero no aplicado (sin assignee) -> nota honesta
        stored[0]["resolved"] = False
        not_resolved = await client.update_task_comment(comment_id="c10", resolved=True, task_id="t1")
        assert not_resolved["resolved"] is False and "note" in not_resolved

    asyncio.run(run())
    print("[PASS] ClickUp comment refetch & ack OK")


def test_clickup_comment_pagination_hint():
    async def run():
        async def fake_request(method, path, *, params=None, json_body=None):
            return {"comments": [
                {"id": str(1000 + i), "comment_text": f"c{i}", "date": str(1790651879000 + i)}
                for i in range(25)
            ]}

        client = ClickUpClient(api_token="pk_test")
        client._request = fake_request  # type: ignore[method-assign]

        listed = await client.list_task_comments(task_id="t1")
        assert listed["count"] == 25
        assert listed["next_page"] == {"start": 1790651879024, "start_id": "1024"}

        # con menos de 25 no hay pista
        async def few(method, path, *, params=None, json_body=None):
            return {"comments": [{"id": "1", "comment_text": "solo", "date": "1790651879000"}]}

        client._request = few  # type: ignore[method-assign]
        assert "next_page" not in await client.list_task_comments(task_id="t1")

    asyncio.run(run())
    print("[PASS] ClickUp comment pagination hint OK")


if __name__ == "__main__":
    test_clickup_comments_client_crud()
    test_clickup_comments_tools_and_dispatch()
    test_clickup_comment_refetch_and_ack()
    test_clickup_comment_pagination_hint()
    print("\nALL CLICKUP COMMENT TESTS PASSED SUCCESSFULLY!")
