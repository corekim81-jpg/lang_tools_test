"""No external client is initialized here."""

from statistics import mean

from lab.common import answer, cases, save_json, score_answer, scrub, stamp


def run() -> dict:
    report = {"mode": "offline-mock", "id": stamp(), "experiments": {}}
    for variant in ("baseline", "good"):
        rows = []
        for case in cases():
            output = answer(case["inputs"], variant=variant)
            rows.append(
                {
                    "id": case["id"],
                    "inputs": case["inputs"],
                    "outputs": output,
                    "scores": score_answer(output["answer"], case["outputs"]),
                }
            )
        report["experiments"][variant] = {
            "rows": rows,
            "averages": {key: mean(r["scores"][key] for r in rows) for key in rows[0]["scores"]},
        }
    report["masking"] = scrub({"email": "demo@example.com", "api_key": "synthetic-example"})
    report["note"] = "로컬 규칙 기반 실습입니다. 서비스 연동 또는 실제 LLM 품질 검증이 아닙니다."
    path = save_json("offline-report.json", report)
    print(f"로컬 실습 완료: {path}")
    for name, result in report["experiments"].items():
        print(name, result["averages"])
    return report
