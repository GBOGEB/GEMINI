"""Native positive/negative controls for the inert federation policy."""
import copy
import json
import unittest
from pathlib import Path

from src.federation_config import PolicyError, validate

DATA=json.loads((Path(__file__).resolve().parents[1]/"config/federation/governed_broker.v1.json").read_text())

class PolicyTests(unittest.TestCase):
    def reject(self,change,code):
        c=copy.deepcopy(DATA);change(c)
        with self.assertRaisesRegex(PolicyError,code):validate(c)
    def test_valid_and_no_execution(self):
        result=validate(copy.deepcopy(DATA))
        self.assertEqual(result["verdict"],"PASS_CONTRACT_ONLY")
        self.assertFalse(result["execution_authorized"])
    def test_default_branch_write(self):
        self.reject(lambda c:c.update(write_to_default_branch=True),"UNAUTHORIZED")
    def test_auto_merge(self):
        self.reject(lambda c:c.update(auto_merge=True),"UNAUTHORIZED")
    def test_fake_installation(self):
        self.reject(lambda c:c.update(app_installation_verified=True),"UNAUTHORIZED")
    def test_fake_drive_writer(self):
        self.reject(lambda c:c.update(drive_writer_authorized=True),"UNAUTHORIZED")
    def test_webhook(self):
        self.reject(lambda c:c.update(webhook_active=True),"UNAUTHORIZED")
    def test_review_required(self):
        self.reject(lambda c:c.update(require_independent_review=False),"MISSING")
    def test_head_ci_required(self):
        self.reject(lambda c:c.update(require_exact_head_ci=False),"MISSING")
    def test_hub_master(self):
        self.reject(lambda c:c["default_branches"].update({"GBOGEB/pipeline-automation-hub":"main"}),"INVALID")
    def test_cycle(self):
        self.reject(lambda c:c["dag"][0].update(deps=["draft_pr_plan"]),"CYCLE")
    def test_missing_dependency(self):
        self.reject(lambda c:c["dag"][1].update(deps=["ghost"]),"UNKNOWN")
    def test_duplicate(self):
        self.reject(lambda c:c["dag"].append(copy.deepcopy(c["dag"][0])),"DUPLICATE")
    def test_exclusive_collision(self):
        def collision(c):
            c["dag"][2]["resources"]=["same/path"]
            c["dag"][3]["resources"]=["same/path"]
        self.reject(collision,"PARALLEL_RESOURCE_COLLISION")
    def test_serial_resource_legal(self):
        c=copy.deepcopy(DATA);c["dag"][0]["resources"]=["same"];c["dag"][1]["resources"]=["same"]
        self.assertEqual(validate(c)["verdict"],"PASS_CONTRACT_ONLY")
