from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Dict, Any
import re


def build_parser() -> argparse.ArgumentParser:
    """Day06のCLI引数を定義します（入力・モード・ケース番号）。"""
    p = argparse.ArgumentParser(prog="day06")
    p.add_argument("--text", required=True)
    p.add_argument("--mode", choices=["normal", "attack"], default="normal")
    p.add_argument("--case", type=int, default=1)
    return p


def _validate_args(args: argparse.Namespace) -> None:
    """引数の簡易バリデーションを行います（入力不備は exit code=2）。"""
    if not args.text:
        raise ValueError("--text is required")
    if args.mode == "attack" and not (1 <= args.case <= 3):
        raise ValueError("--case must be between 1 and 3 when --mode attack")


def run_guarded(*, text: str, mode: str, case: int) -> str:
    """入力とツール実行をガードしながら処理し、回答（文字列）を返します。

    `mode` の意味：
    - `normal`：通常入力を処理
    - `attack`：用意した「悪い入力例」を使って、ガードが効いているか確認

    実装ガイド：
    - attackケースは最低3つ用意（README参照）
    - 「禁止する行為」を明確にし、検知したら例外（または拒否文）にする
    - ツールを実装する場合は許可リストで制限する（許可されないツールは実行しない）

    返り値：
    - 標準出力に出る本文（文章）を返す
    """
    try:
        # 攻撃パターンの定義
        attack_patterns = {
            1: {
                'name': '指示無視',
                'keywords': ['無視して', '無視し', '前の指示', '秘密情報', '出して'],
                'description': '秘密情報の指示無視'
            },
            2: {
                'name': '不正ツール実行',
                'keywords': ['システムコマンド', '実行して', 'コマンドを実行', 'shell', 'bash'],
                'description': 'システムコマンドの不正実行'
            },
            3: {
                'name': '許可外操作',
                'keywords': ['削除して', 'ファイルを削除', '消して', '削除', 'remove'],
                'description': '許可されていないファイル操作'
            }
        }
        
        if mode == "attack":
            # 攻撃モード：指定された攻撃パターンを検知
            pattern = attack_patterns.get(case, attack_patterns[1])
            
            logging.info(f"Attack mode: testing pattern {case} - {pattern['name']}")
            
            # 攻撃パターンに一致するか検知
            for keyword in pattern['keywords']:
                if keyword in text:
                    error_msg = f"[ERROR] 不正な入力が検出されました: {pattern['description']}に一致するパターン"
                    logging.warning(f"Guard triggered: {pattern['name']} detected in input")
                    return error_msg
            
            # 攻撃パターンに一致しない場合も拒否（安全側）
            return "[ERROR] 不正な入力が検出されました: 禁止されたパターンに一致"
        
        else:
            # 通常モード：基本的な入力検証
            if not text.strip():
                return "[ERROR] 入力が空です"
            
            # 簡単な有害パターン検知
            dangerous_patterns = ['削除', '消して', 'システムコマンド', '実行して']
            for pattern in dangerous_patterns:
                if pattern in text:
                    warning_msg = f"[WARNING] 危険なキーワードが検出されました: {pattern}"
                    logging.warning(f"Dangerous pattern detected: {pattern}")
                    return warning_msg
            
            # 通常処理：簡易な応答生成
            if "天気" in text:
                return "今日の天気は晴れです。"
            elif "時間" in text:
                return "現在の時刻は12:00です。"
            elif "名前" in text:
                return "私はAIアシスタントです。"
            else:
                return "ご質問ありがとうございます。通常モードで処理しました。"
        
    except Exception as e:
        error_msg = f"[ERROR] 処理中にエラーが発生しました: {str(e)}"
        logging.error(f"Guard processing failed: {e}")
        return error_msg


def main(argv: List[str] | None = None) -> int:
    """CLIのエントリポイントです。

    受講者は `run_guarded()` を実装します。ここは引数解析/検証/終了コードを担当します。
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    try:
        _validate_args(args)
    except Exception as e:
        logging.error(str(e))
        print(str(e), file=sys.stderr)
        return 2

    logging.info("mode=%s case=%s", args.mode, args.case)

    try:
        out = run_guarded(text=args.text, mode=args.mode, case=args.case)
        print(out)
        return 0
    except NotImplementedError as e:
        logging.error(str(e))
        print(str(e), file=sys.stderr)
        return 1
    except Exception as e:
        logging.error("%s", e)
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
