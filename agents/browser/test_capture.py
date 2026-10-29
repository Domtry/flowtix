"""Automated test: start recording, simulate clicks, verify events are captured."""

import asyncio
import json
import time

import httpx

AGENT = "http://localhost:9090"


async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # 1. Start recording
        print("1. Starting recording on https://example.com ...")
        resp = await c.post(f"{AGENT}/record/start", json={"target_url": "https://example.com"})
        assert resp.status_code == 200, f"Start failed: {resp.text}"
        sid = resp.json()["session_id"]
        print(f"   Session: {sid}")

        await asyncio.sleep(2)

        # 2. Check debug info
        print("2. Checking capture script injection ...")
        resp = await c.get(f"{AGENT}/record/{sid}/debug")
        debug = resp.json()
        print(f"   capture_status: {json.dumps(debug['capture_status'], indent=2)}")
        print(f"   python_events: {debug['python_events']}")

        assert debug["capture_status"].get("recording") is True, "Script NOT injected!"
        assert debug["capture_status"].get("pushFn") == "function", "__flowtix_push NOT available!"
        print("   -> Script injected, expose_function active")

        # 3. Simulate a click via agent
        print("3. Simulating a programmatic click ...")
        resp = await c.post(f"{AGENT}/record/{sid}/test-click")
        click_result = resp.json()
        print(f"   {click_result}")

        # 4. Collect events
        print("4. Collecting events ...")
        resp = await c.get(f"{AGENT}/record/{sid}/events")
        events = resp.json()
        print(f"   Total events: {len(events)}")
        for ev in events:
            t = ev.get("event_type", "?")
            sel = ev.get("target", {}).get("selector", "")
            val = ev.get("value", "")
            print(f"   [{t:12s}] {sel[:60]}  {val[:30]}")

        click_events = [e for e in events if e["event_type"] == "click"]
        print(f"\n   Click events captured: {len(click_events)}")

        if click_events:
            print("\n   CLICK CAPTURE WORKS!")
        else:
            print("\n   WARNING: No click events — check page or capture script")

        # 5. Stop recording
        print("\n5. Stopping recording ...")
        resp = await c.post(f"{AGENT}/record/{sid}/stop")
        data = resp.json()
        steps = data.get("definition", {}).get("process", {}).get("steps", [])
        print(f"   Events: {data['event_count']}, Steps generated: {len(steps)}")
        for s in steps:
            print(f"   [{s['type']:20s}] {s.get('label', '')}")

        print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
