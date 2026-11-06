import argparse
import hashlib
import json
from pathlib import Path

from .ledger import Ledger, encode


def digest(content):
    return hashlib.sha256(content.encode("ascii")).hexdigest()


def snapshot(root, configuration, residual, invariant_version):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("evaluator must be a regular directory")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("evaluator tree contains a link or special file")
        if path.name.lower() in {"auth.json", "credentials", "tokens"}:
            raise ValueError("evaluator tree contains a forbidden credential filename")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_bytes().hex()
    if (not files or not isinstance(configuration, dict)
            or not isinstance(residual, str) or not residual
            or not isinstance(invariant_version, str) or not invariant_version):
        raise ValueError("code, configuration, residual and invariant version are required")
    return encode(dict(files=files, configuration=configuration, residual=residual,
                       invariant_version=invariant_version))


def validate_frozen(record, prior):
    data = record["data"]
    siblings = [r for r in prior.values() if r["kind"] == "frozen_evaluator"
                and r["data"]["task"] == data["task"]]
    for old in siblings:
        failed = any(r["kind"] == "receipt" and r["data"]["frozen_evaluator"] == old["id"]
                     and r["data"]["outcome_state"] in {"failed", "failed_with_test_concern"}
                     for r in prior.values())
        if failed and old["data"]["content"] != data["content"]:
            raise ValueError("evaluator edit after recorded failure is forbidden")
    if "freeze" not in data:
        if "revision" in data or any("freeze" in r["data"] for r in siblings):
            raise ValueError("revision requires a frozen content digest")
        return
    freeze = data["freeze"]
    if freeze["digest"] != digest(data["content"]):
        raise ValueError("frozen content digest differs")
    if record["id"] != "evr:" + digest(encode(data)):
        raise ValueError("frozen evaluator identity differs from content")
    bundle = json.loads(data["content"])
    if (not isinstance(bundle, dict) or set(bundle) != {
            "files", "configuration", "residual", "invariant_version"}
            or encode(bundle) != data["content"] or not isinstance(bundle["files"], dict)
            or not bundle["files"] or not isinstance(bundle["configuration"], dict)
            or any(not isinstance(bundle[k], str) or not bundle[k]
                   for k in ("residual", "invariant_version"))):
        raise ValueError("invalid frozen bundle")
    for name, content in bundle["files"].items():
        if (Path(name).is_absolute() or not name or Path(name).as_posix() != name
                or ".." in Path(name).parts or not isinstance(content, str)
                or bytes.fromhex(content).hex() != content):
            raise ValueError("invalid frozen file")
    if data["admitted_input"] not in freeze["synthesis_context"]["inputs"]:
        raise ValueError("synthesis context must include the admitted input")
    for identity in freeze["synthesis_context"]["inputs"]:
        source = prior.get(identity)
        if source is None or source["kind"] not in {"task", "admitted_input"}:
            raise ValueError("synthesis context must contain only durable candidate-blind inputs")
        task = source["id"] if source["kind"] == "task" else source["data"]["task"]
        if task != data["task"]:
            raise ValueError("synthesis context belongs to a different task")
    if siblings:
        revision = data.get("revision", {})
        if revision.get("of") != siblings[-1]["id"]:
            raise ValueError("revision must reference the latest frozen evaluator")
        evidence = prior.get(revision.get("evidence"))
        if (evidence is None or evidence["kind"] != "admitted_input"
                or evidence["data"]["task"] != data["task"]):
            raise ValueError("revision requires outcome-independent admitted evidence")
    elif "revision" in data:
        raise ValueError("revision has no prior evaluator")


class FrozenEvaluators:
    def __init__(self, ledger):
        self.ledger = ledger

    def freeze(self, root, *, task, admitted_input, confirmed_by, qualification,
               synthesis_context, configuration, residual, invariant_version, revision=None):
        content = snapshot(root, configuration, residual, invariant_version)
        data = dict(task=task, admitted_input=admitted_input, content=content,
                    confirmed_by=confirmed_by,
                    freeze=dict(digest=digest(content), qualification=qualification,
                                synthesis_context=synthesis_context))
        if revision is not None:
            data["revision"] = revision
        record = dict(version=0, kind="frozen_evaluator", id="evr:" + digest(encode(data)), data=data)
        self.ledger.append(record)
        return record

    def require_frozen(self, identity, root, *, configuration, residual, invariant_version):
        record = next((r for r in self.ledger.records() if r["id"] == identity), None)
        if record is None or record["kind"] != "frozen_evaluator" or "freeze" not in record["data"]:
            raise ValueError("evaluation requires a content-hashed frozen evaluator")
        content = snapshot(root, configuration, residual, invariant_version)
        if digest(content) != record["data"]["freeze"]["digest"]:
            raise ValueError("running evaluator tree digest differs from frozen record")
        return json.loads(record["data"]["content"])

    def evaluate(self, root, receipt, judge, **components):
        receipt = json.loads(encode(receipt))
        data = receipt["data"]
        bundle = self.require_frozen(data["frozen_evaluator"], root, **components)
        data.update(delivery_state="running", outcome_state="unobserved", observations=[])
        self.ledger.append(receipt | {"id": receipt["id"] + ":started"})
        outcome, observations = judge(bundle)
        data.update(delivery_state="finished", outcome_state=outcome, observations=observations)
        self.ledger.append(receipt)
        return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["freeze"])
    parser.add_argument("ledger")
    parser.add_argument("tree")
    parser.add_argument("manifest")
    args = parser.parse_args()
    try:
        result = FrozenEvaluators(Ledger(args.ledger)).freeze(
            args.tree, **json.loads(Path(args.manifest).read_text()))
        print(result["id"])
    except (ValueError, OSError, TypeError) as error:
        parser.exit(2, f"freeze refused: {error}\n")


if __name__ == "__main__":
    main()
