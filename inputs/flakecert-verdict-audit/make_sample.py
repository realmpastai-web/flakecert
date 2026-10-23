#!/usr/bin/env python3
"""Writes sample/dd-test-run.json: a test run in the dd-trace 6.21.0 citestcycle event shape
(type/version/content{name,resource,service,meta,metrics}), JSON instead of msgpack. Tag keys and
values are the ones the shipped tracer writes (see sources/). Synthetic test names; no Datadog account."""
import json
def ev(suite, name, status, **meta):
    m = {"test.suite": suite, "test.name": name, "test.status": status, "test.framework": "jest",
         "test.type": "test", "test_session_id": "1", "test_module_id": "2", "test_suite_id": "3"}
    m.update(meta)
    return {"type": "test", "version": 2, "content": {"name": "jest.test", "resource": f"{suite}.{name}",
            "service": "sample", "meta": m, "metrics": {}}}
def atf(suite, name, statuses):
    out = []
    for i, s in enumerate(statuses):
        meta = {"test.test_management.is_attempt_to_fix": "true"}
        if i > 0:
            meta.update({"test.is_retry": "true", "test.retry_reason": "attempt_to_fix"})
        if i == len(statuses) - 1:
            meta["test.test_management.attempt_to_fix_passed"] = "true" if "fail" not in statuses else "false"
        out.append(ev(suite, name, s, **meta))
    return out
events = []
events += atf("cart.test.js", "total rounds to cents", ["pass"] * 20)            # default 20 retries, all pass
events += atf("sync.test.js", "drains queue", ["pass"] * 50)                     # policy set to 50, all pass
events += atf("auth.test.js", "token refresh", ["pass"] * 12 + ["fail"] + ["pass"] * 7)  # one failure
events += [ev("search.test.js", "ranks exact match", "fail"),
           ev("search.test.js", "ranks exact match", "pass", **{"test.is_retry": "true", "test.retry_reason": "auto_test_retry"})]
doc = {"version": 1, "metadata": {"*": {"language": "javascript", "library_version": "6.21.0"}}, "events": events}
json.dump(doc, open("sample/dd-test-run.json", "w"), indent=1, sort_keys=True); open("sample/dd-test-run.json", "a").write("\n")
print("events", len(events))
