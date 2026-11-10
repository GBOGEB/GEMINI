"""Read-only federation policy/DAG guard. No GitHub/Drive writes or token usage."""
import json
import sys
from collections import deque
from pathlib import Path

REPOS = {"GBOGEB/GEMINI":"main","GBOGEB/pipeline-automation-hub":"master",
         "GBOGEB/CODEX":"main","GBOGEB/ABACUS":"main","GBOGEB/gg_MATH":"main",
         "GBOGEB/cryoplant-project":"main","GBOGEB/DOCX_RTM_Automation":"main"}


class PolicyError(ValueError):
    pass


def deny_if(condition, code):
    if condition:
        raise PolicyError(code)


def validate(c):
    deny_if(not isinstance(c, dict) or c.get("schema") != "gmi.federation_config.v1", "BAD_SCHEMA")
    deny_if(c.get("status") != "INERT_POLICY_ONLY", "EXECUTION_NOT_AUTHORIZED")
    for k in ("app_installation_verified","drive_writer_authorized","webhook_active",
              "write_to_default_branch","auto_merge"):
        deny_if(c.get(k) is not False, "UNAUTHORIZED_"+k.upper())
    for k in ("require_draft_pr","require_exact_head_ci","require_independent_review"):
        deny_if(c.get(k) is not True, "MISSING_"+k.upper())
    deny_if(c.get("default_branches") != REPOS, "INVALID_REPO_BRANCH_REGISTRY")
    nodes = c.get("dag")
    deny_if(not isinstance(nodes, list) or not nodes, "EMPTY_DAG")
    ids = [n.get("id") for n in nodes]
    deny_if(any(not isinstance(i,str) or not i for i in ids), "INVALID_NODE")
    deny_if(len(ids) != len(set(ids)), "DUPLICATE_NODE")
    inc = {i:0 for i in ids}
    out = {i:[] for i in ids}
    resources = {}
    for n in nodes:
        ident = n["id"]
        deps, r = n.get("deps"), n.get("resources")
        deny_if(not isinstance(deps,list) or len(deps)!=len(set(deps)), "BAD_DEPENDENCIES")
        deny_if(any(d not in inc or d == ident for d in deps), "UNKNOWN_PREDECESSOR")
        deny_if(not isinstance(r,list) or len(r)!=len(set(r)) or
                any(not isinstance(x,str) or not x or ".." in x.split("/") for x in r), "BAD_RESOURCES")
        resources[ident]=set(r)
        inc[ident]=len(deps)
        for d in deps:out[d].append(ident)
    ready=deque(sorted(x for x in ids if inc[x]==0))
    result=[]
    while ready:
        x=ready.popleft()
        result.append(x)
        for y in out[x]:
            inc[y]-=1
            if inc[y]==0:ready.append(y)
        ready=deque(sorted(ready))
    deny_if(len(result)!=len(ids),"CYCLE_DETECTED")
    ancestors={x:set() for x in ids}
    depmap={n["id"]:n["deps"] for n in nodes}
    for x in result:
        for d in depmap[x]:
            ancestors[x].add(d)
            ancestors[x].update(ancestors[d])
    for j,a in enumerate(ids):
        for b in ids[j+1:]:
            if a not in ancestors[b] and b not in ancestors[a]:
                deny_if(bool(resources[a] & resources[b]), "PARALLEL_RESOURCE_COLLISION")
    return {"verdict":"PASS_CONTRACT_ONLY","execution_authorized":False,"nodes":len(ids),"order":result}


if __name__ == "__main__":
    try:
        path=Path(sys.argv[1]) if len(sys.argv)>1 else Path("config/federation/governed_broker.v1.json")
        print(json.dumps(validate(json.loads(path.read_text(encoding="utf-8"))),indent=2))
    except (PolicyError,ValueError,OSError,IndexError) as e:
        print(json.dumps({"verdict":"DENY","reason":str(e)}),file=sys.stderr)
        raise SystemExit(2)
