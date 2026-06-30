from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import signal
from typing import Any, Dict, List
from contextlib import contextmanager


@contextmanager
def timeout_context(seconds: int):
    """タイムアウト処理のためのコンテキストマネージャ"""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Windowsではsignal.SIGALRMが使えないので、簡易的なタイムアウトチェック
    start_time = time.time()
    
    class TimeoutChecker:
        def check_timeout(self):
            if time.time() - start_time > seconds:
                raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    checker = TimeoutChecker()
    yield checker


def load_suite(path: str) -> List[Dict[str, Any]]:
    """テスト入力セットを読み込んでケース配列を返します。

    形式は自由ですが、まずはJSONを推奨します。

    例（suite.json）：
    - `[{"id":"case1","input":"..."}, {"id":"case2","input":"..."}]`

    実装ガイド：
    - `path` を開いて読み、ケース配列（list[dict]）にして返す
    - ケースは最低 `id` と `input` を含む想定
    """
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Suite file not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            suite = json.load(f)
        
        if not isinstance(suite, list):
            raise ValueError("Suite must be a list of test cases")
        
        # 各ケースの必須フィールドをチェック
        for i, case in enumerate(suite):
            if not isinstance(case, dict):
                raise ValueError(f"Case {i} must be a dictionary")
            if 'id' not in case:
                raise ValueError(f"Case {i} missing required field: 'id'")
            if 'input' not in case:
                raise ValueError(f"Case {i} missing required field: 'input'")
        
        logging.info(f"Loaded {len(suite)} test cases from {path}")
        return suite
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in suite file: {e}")
    except Exception as e:
        raise Exception(f"Failed to load suite: {e}")


def run_case(case: Dict[str, Any], timeout_sec: int) -> Dict[str, Any]:
    """1ケースを実行して結果dictを返します。

    実装ガイド：
    - ここでは「どのDayの成果物を評価するか」を決めて呼び出してください
      例：Day08のフローを呼ぶ、または最終課題を呼ぶ、など
    - 戻り値は最低限このキーを含めると扱いやすいです
      - `id`: ケースID
      - `passed`: bool
      - `reason`: str（失敗理由）
      - `output`: 任意（実際の出力）

    注意：
    - `timeout_sec` を使って、長時間実行にならないようにしてください
    """
    case_id = case.get('id', 'unknown')
    input_text = case.get('input', '')
    
    result = {
        'id': case_id,
        'input': input_text,
        'passed': False,
        'reason': '',
        'output': '',
        'error': ''
    }
    
    try:
        with timeout_context(timeout_sec) as checker:
            checker.check_timeout()
            
            # Day08のフローを呼び出して評価
            from day08.app import run_graph
            
            # 基本的なバリデーション
            if not input_text.strip():
                result['passed'] = False
                result['reason'] = 'Empty input'
                result['output'] = '[ERROR] 入力が空です'
                return result
            
            # Day08の実行（簡易的なパラメータ）
            output = run_graph(text=input_text, max_steps=5, max_retry=1)
            
            checker.check_timeout()
            
            # 基本的な成功判定
            if output and '[ERROR]' not in output:
                result['passed'] = True
                result['reason'] = 'Success'
                result['output'] = output
            else:
                result['passed'] = False
                result['reason'] = 'Processing failed or error in output'
                result['output'] = output
            
    except TimeoutError as e:
        result['passed'] = False
        result['reason'] = f'Timeout: {str(e)}'
        result['error'] = str(e)
        
    except Exception as e:
        result['passed'] = False
        result['reason'] = f'Exception: {str(e)}'
        result['error'] = str(e)
    
    return result


def build_parser() -> argparse.ArgumentParser:
    """Day09のCLI引数を定義します（suite入力と出力先）。"""
    p = argparse.ArgumentParser(prog="day09")
    p.add_argument("--suite", required=True)
    p.add_argument("--out", default=os.path.join("day09", "result.json"))
    p.add_argument("--timeout-sec", type=int, default=30)
    return p


def _validate_args(args: argparse.Namespace) -> None:
    """引数の簡易バリデーションを行います（入力不備は exit code=2）。"""
    if not args.suite:
        raise ValueError("--suite is required")
    if args.timeout_sec <= 0:
        raise Exception("--timeout-sec must be a positive integer")


def load_suite(path: str) -> List[Dict[str, Any]]:
    """テスト入力セットを読み込んでケース配列を返します。

    形式は自由ですが、まずはJSONを推奨します。

    例（suite.json）：
    - `[{"id":"case1","input":"..."}, {"id":"case2","input":"..."}]`

    実装ガイド：
    - `path` を開いて読み、ケース配列（list[dict]）にして返す
    - ケースは最低 `id` と `input` を含む想定
    """
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Suite file not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            suite = json.load(f)
        
        if not isinstance(suite, list):
            raise ValueError("Suite must be a list of test cases")
        
        # 各ケースの必須フィールドをチェック
        for i, case in enumerate(suite):
            if not isinstance(case, dict):
                raise ValueError(f"Case {i} must be a dictionary")
            if 'id' not in case:
                raise ValueError(f"Case {i} missing required field: 'id'")
            if 'input' not in case:
                raise ValueError(f"Case {i} missing required field: 'input'")
        
        logging.info(f"Loaded {len(suite)} test cases from {path}")
        return suite
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in suite file: {e}")
    except Exception as e:
        raise Exception(f"Failed to load suite: {e}")


def run_case(case: Dict[str, Any], timeout_sec: int) -> Dict[str, Any]:
    """1ケースを実行して結果dictを返します。"""
    case_id = case.get('id', 'unknown')
    input_text = case.get('input', '')
    
    result = {
        'id': case_id,
        'input': input_text,
        'passed': False,
        'reason': '',
        'output': '',
        'error': ''
    }
    
    try:
        with timeout_context(timeout_sec) as checker:
            checker.check_timeout()
            
            # Day08のフローを呼び出して評価
            from day08.app import run_graph
            
            # 基本的なバリデーション
            if not input_text.strip():
                result['passed'] = False
                result['reason'] = 'Empty input'
                result['output'] = '[ERROR] 入力が空です'
                return result
            
            # Day08の実行（簡易的なパラメータ）
            output = run_graph(text=input_text, max_steps=5, max_retry=1)
            
            checker.check_timeout()
            
            # 基本的な成功判定
            if output and '[ERROR]' not in output:
                result['passed'] = True
                result['reason'] = 'Success'
                result['output'] = output
            else:
                result['passed'] = False
                result['reason'] = 'Processing failed or error in output'
                result['output'] = output
            
    except TimeoutError as e:
        result['passed'] = False
        result['reason'] = f'Timeout: {str(e)}'
        result['error'] = str(e)
        
    except Exception as e:
        result['passed'] = False
        result['reason'] = f'Exception: {str(e)}'
        result['error'] = str(e)
    
    return result


def main(argv: List[str] | None = None) -> int:
    """CLIのエントリポイントです。

    suite読み込み→各ケース実行→結果JSON出力までを制御します。
    受講者は `load_suite()` と `run_case()` を実装します。
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    try:
        _validate_args(args)
    except Exception as e:
        logging.error(str(e))
        print(str(e), file=sys.stderr)
        return 2

    try:
        suite = load_suite(args.suite)
        results: List[Dict[str, Any]] = []
        ok = 0
        ng = 0

        for case in suite:
            start = time.perf_counter()
            try:
                r = run_case(case, timeout_sec=args.timeout_sec)
                r.setdefault("duration_ms", int((time.perf_counter() - start) * 1000))
                passed = bool(r.get("passed", False))
                ok += 1 if passed else 0
                ng += 0 if passed else 1
                results.append(r)
            except NotImplementedError as e:
                logging.error(str(e))
                print(str(e), file=sys.stderr)
                return 1

        out_obj = {
            "summary": {"passed": ok, "failed": ng, "total": ok + ng},
            "results": results,
        }
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)

        print(f"passed={ok} failed={ng} total={ok + ng}")
        return 0
    except Exception as e:
        logging.error("%s", e)
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
