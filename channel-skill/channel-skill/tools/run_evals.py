#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_evals.py 1.0.0

Прогон эталонов поведения скилла: маршрут, линтер, оценка, разрез, крючки,
память и речь в чате. Случаи лежат в evals/cases.json, цифры в них сняты
с живого вывода инструментов.

Гонять:
  python3 tools/run_evals.py
  python3 tools/run_evals.py --case route-abuz --case lint-slop
  python3 tools/run_evals.py --list
  python3 tools/run_evals.py --json
  python3 tools/run_evals.py --selftest

Формат случая:
  id        имя, по которому его можно гонять поодиночке
  why       зачем этот случай вообще есть
  args      аргументы питона, первый из них путь от корня скилла
  exit      ожидаемый код возврата
  contains  строки, которые обязаны быть в выводе
  forbidden строки, которых быть не должно
  json      разобрать вывод как json
  codes     коды линтера, которые обязаны прийти
  no_codes  коды, которых быть не должно (ложные срабатывания)
  numbers   проверки полей: field плюс min, max, equals или contains
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

VERSION = "6.1.0"
DEFAULT_TIMEOUT = 120


def skill_root():
    env = os.environ.get("CHANNEL_SKILL_DIR")
    if env:
        return os.path.abspath(env)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def load_cases(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    cases = data.get("cases") or []
    seen = set()
    for case in cases:
        cid = case.get("id")
        if not cid:
            raise ValueError("в случае нет поля id")
        if cid in seen:
            raise ValueError("два случая с одним id: %s" % cid)
        seen.add(cid)
        if not case.get("args"):
            raise ValueError("в случае %s нет args" % cid)
    return cases


def field_value(payload, dotted):
    current = payload
    for part in str(dotted).split("."):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def codes_in(payload):
    found = set()
    for key in ("errors", "warns", "warnings"):
        for item in payload.get(key) or []:
            if isinstance(item, dict) and item.get("code"):
                found.add(item["code"])
    return found


def run_case(case, root, timeout=DEFAULT_TIMEOUT):
    cmd = [sys.executable] + [str(a) for a in case["args"]]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(cmd, cwd=root, env=env, timeout=timeout,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        return {"id": case["id"], "ok": False, "output": "",
                "reasons": ["не уложился в %d секунд" % timeout]}
    output = proc.stdout.decode("utf-8", "replace")
    reasons = []

    want_exit = case.get("exit")
    if want_exit is not None and proc.returncode != want_exit:
        reasons.append("код возврата %d, а ждали %d" % (proc.returncode, want_exit))
    for needle in case.get("contains") or []:
        if needle not in output:
            reasons.append("нет строки: %s" % needle)
    for needle in case.get("forbidden") or []:
        if needle in output:
            reasons.append("лишняя строка: %s" % needle)

    payload = None
    if case.get("json"):
        try:
            payload = json.loads(output)
        except ValueError:
            reasons.append("вывод не разобрался как json")

    if payload is not None:
        got = codes_in(payload)
        for code in case.get("codes") or []:
            if code not in got:
                reasons.append("нет кода %s, пришли: %s" % (code, ", ".join(sorted(got)) or "ни одного"))
        for code in case.get("no_codes") or []:
            if code in got:
                reasons.append("ложное срабатывание: лишний код %s" % code)
        for rule in case.get("numbers") or []:
            name = rule.get("field")
            try:
                value = field_value(payload, name)
            except (KeyError, IndexError, TypeError, ValueError):
                reasons.append("нет поля %s" % name)
                continue
            if "equals" in rule and value != rule["equals"]:
                reasons.append("поле %s = %r, а ждали %r" % (name, value, rule["equals"]))
            if "contains" in rule and str(rule["contains"]) not in str(value):
                reasons.append("в поле %s нет %r, там %r" % (name, rule["contains"], value))
            for bound, sign in (("min", "ниже"), ("max", "выше")):
                if bound not in rule:
                    continue
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    reasons.append("поле %s не число: %r" % (name, value))
                    break
                if bound == "min" and value < rule["min"]:
                    reasons.append("поле %s = %s, %s порога %s" % (name, value, sign, rule["min"]))
                if bound == "max" and value > rule["max"]:
                    reasons.append("поле %s = %s, %s потолка %s" % (name, value, sign, rule["max"]))

    return {"id": case["id"], "ok": not reasons, "reasons": reasons, "output": output,
            "why": case.get("why", "")}


def run_suite(cases, root, only=None, timeout=DEFAULT_TIMEOUT):
    picked = [c for c in cases if not only or c["id"] in only]
    return [run_case(case, root, timeout) for case in picked], picked


def selftest():
    """Проверяет сам раннер на временных скриптах, без живого скилла."""
    fails = []

    def check(name, condition, extra=""):
        print("%s %s%s" % ("PASS" if condition else "FAIL", name,
                           (" " + extra) if extra and not condition else ""))
        if not condition:
            fails.append(name)

    tmp = tempfile.mkdtemp(prefix="channel-evals-")
    try:
        with open(os.path.join(tmp, "probe.py"), "w", encoding="utf-8") as handle:
            handle.write("print('\u041e\u041a \u043f\u0440\u043e\u0431\u0430')\n")
        with open(os.path.join(tmp, "probe_json.py"), "w", encoding="utf-8") as handle:
            handle.write("import json\n"
                         "print(json.dumps({'total': 77, 'verdict': '\u043f\u043e\u0447\u0442\u0438',"
                         " 'errors': [{'code': 'E-TEST'}], 'warns': [{'code': 'W-TEST'}]}))\n"
                         "raise SystemExit(1)\n")

        ok_case = {"id": "probe-ok", "args": ["probe.py"], "exit": 0, "contains": ["\u041e\u041a"]}
        check("чистый случай проходит", run_case(ok_case, tmp)["ok"])

        bad_text = {"id": "probe-text", "args": ["probe.py"], "contains": ["\u0447\u0435\u043f\u0443\u0445\u0430"]}
        res = run_case(bad_text, tmp)
        check("ловит отсутствие строки", not res["ok"] and "нет строки" in res["reasons"][0])

        bad_exit = {"id": "probe-exit", "args": ["probe.py"], "exit": 3}
        check("ловит чужой код возврата", not run_case(bad_exit, tmp)["ok"])

        forbidden = {"id": "probe-forbidden", "args": ["probe.py"], "forbidden": ["\u041e\u041a"]}
        check("ловит запретную строку", not run_case(forbidden, tmp)["ok"])

        codes_ok = {"id": "probe-codes", "args": ["probe_json.py"], "exit": 1, "json": True,
                    "codes": ["E-TEST", "W-TEST"]}
        check("видит коды и в errors, и в warns", run_case(codes_ok, tmp)["ok"])

        codes_bad = {"id": "probe-codes-bad", "args": ["probe_json.py"], "exit": 1, "json": True,
                     "no_codes": ["E-TEST"]}
        check("ловит ложное срабатывание", not run_case(codes_bad, tmp)["ok"])

        num_ok = {"id": "probe-num", "args": ["probe_json.py"], "exit": 1, "json": True,
                  "numbers": [{"field": "total", "min": 70, "max": 80},
                              {"field": "verdict", "contains": "\u043f\u043e\u0447\u0442\u0438"}]}
        check("числовой коридор сходится", run_case(num_ok, tmp)["ok"])

        num_bad = {"id": "probe-num-bad", "args": ["probe_json.py"], "exit": 1, "json": True,
                   "numbers": [{"field": "total", "min": 90}]}
        res = run_case(num_bad, tmp)
        check("ловит оценку ниже порога", not res["ok"] and "ниже порога" in res["reasons"][0])

        missing = {"id": "probe-missing", "args": ["probe_json.py"], "exit": 1, "json": True,
                   "numbers": [{"field": "нетутакого", "min": 1}]}
        check("ловит отсутствующее поле", not run_case(missing, tmp)["ok"])

        not_json = {"id": "probe-not-json", "args": ["probe.py"], "json": True, "codes": ["E-TEST"]}
        check("ловит не json вывод", not run_case(not_json, tmp)["ok"])

        # фильтр по id и проверка файла случаев
        cases_path = os.path.join(tmp, "cases.json")
        with open(cases_path, "w", encoding="utf-8") as handle:
            json.dump({"cases": [ok_case, dict(bad_text)]}, handle)
        cases = load_cases(cases_path)
        results, picked = run_suite(cases, tmp, only={"probe-ok"})
        check("фильтр --case берёт ровно один случай", len(picked) == 1 and results[0]["ok"])

        dupe = os.path.join(tmp, "dupe.json")
        with open(dupe, "w", encoding="utf-8") as handle:
            json.dump({"cases": [ok_case, ok_case]}, handle)
        try:
            load_cases(dupe)
            check("ловит два случая с одним id", False)
        except ValueError:
            check("ловит два случая с одним id", True)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("Итого: проверок раннера 12, провалилось %d" % len(fails))
    return 1 if fails else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Прогон эталонов скилла")
    parser.add_argument("--root", help="корень скилла")
    parser.add_argument("--cases", help="файл со случаями")
    parser.add_argument("--case", action="append", default=[], help="гнать только этот id")
    parser.add_argument("--list", action="store_true", help="показать список случаев")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print("run_evals.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()

    root = os.path.abspath(args.root) if args.root else skill_root()
    cases_path = args.cases or os.path.join(root, "evals", "cases.json")
    if not os.path.exists(cases_path):
        print("Нет файла со случаями: %s" % cases_path)
        return 1
    try:
        cases = load_cases(cases_path)
    except ValueError as err:
        print("Случаи собраны неверно: %s" % err)
        return 1

    if args.list:
        for case in cases:
            print("%-22s %s" % (case["id"], case.get("why", "")))
        print("Всего случаев: %d" % len(cases))
        return 0

    only = set(args.case)
    unknown = only - {c["id"] for c in cases}
    if unknown:
        print("Нет таких случаев: %s" % ", ".join(sorted(unknown)))
        return 1

    results, picked = run_suite(cases, root, only=only, timeout=args.timeout)
    failed = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({"root": root, "cases": len(picked),
                          "passed": len(results) - len(failed), "failed": len(failed),
                          "results": [{"id": r["id"], "ok": r["ok"], "reasons": r["reasons"]}
                                      for r in results]},
                         ensure_ascii=False, indent=2))
        return 1 if failed else 0

    print("Эталоны: %d случаев, корень %s" % (len(picked), root))
    for res in results:
        print("%s %s" % ("PASS" if res["ok"] else "FAIL", res["id"]))
        for reason in res["reasons"]:
            print("    %s" % reason)
    print("Итого: прошло %d, провалилось %d" % (len(results) - len(failed), len(failed)))
    if failed:
        first = failed[0]
        print("ПЕРВОЕ РАСХОЖДЕНИЕ: %s -> %s" % (first["id"], first["reasons"][0]))
        print("Зачем этот случай: %s" % (first.get("why") or "описания нет"))
        return 1
    print("Все эталоны сошлись.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
