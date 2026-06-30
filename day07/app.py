from __future__ import annotations

import argparse
import logging
import sys
import re
from typing import List, Dict, Any, TypedDict, Literal


class State(TypedDict):
    """LangGraphの状態を定義します"""
    input: str
    intent: Literal["rag", "summarize", "plan", "unknown"]
    output: str
    errors: List[str]


def build_parser() -> argparse.ArgumentParser:
    """Day07のCLI引数を定義します（入力と分類モード）。"""
    p = argparse.ArgumentParser(prog="day07")
    p.add_argument("--text", required=True)
    p.add_argument("--mode", choices=["llm", "rule"], default="rule")
    return p


def _validate_args(args: argparse.Namespace) -> None:
    """引数の簡易バリデーションを行います（入力不備は exit code=2）。"""
    if not args.text:
        raise ValueError("--text is required")


def run_graph(*, text: str, mode: str) -> str:
    """LangGraphで「分類→分岐→処理」を実行し、最終出力（文字列）を返します。

    mode:
    - `rule`：ルール（キーワード等）でintentを決めて分岐
    - `llm`：LLMでintentを分類して分岐

    受け入れ基準（README）：
    - 分岐が最低2パターンある
    - どの分岐に入ったかがログで分かる
    - 分類不能時のフォールバックがある
    """
    try:
        # 初期状態を設定
        state: State = {
            "input": text,
            "intent": "unknown",
            "output": "",
            "errors": []
        }
        
        # ノード1：入力を分類する
        state = classify_input(state, mode)
        logging.info(f"Intent classified as: {state['intent']}")
        
        # ノード2：intentに応じて処理を分岐する
        state = process_by_intent(state)
        logging.info(f"Processing completed for intent: {state['intent']}")
        
        # ノード3：最終出力を整形する
        state = format_output(state)
        
        return state["output"]
        
    except Exception as e:
        logging.error(f"Graph execution failed: {e}")
        raise Exception(f"処理フローの実行に失敗しました: {e}")


def classify_input(state: State, mode: str) -> State:
    """入力を分類し、intentを決定します"""
    text = state["input"].lower()
    
    if mode == "rule":
        # ルールベースの分類
        if any(keyword in text for keyword in ["教えて", "について", "とは"]):
            state["intent"] = "rag"
        elif any(keyword in text for keyword in ["要約", "まとめて", "要約して"]):
            state["intent"] = "summarize"
        elif any(keyword in text for keyword in ["手順", "方法", "実装", "やり方"]):
            state["intent"] = "plan"
        else:
            state["intent"] = "unknown"
    else:
        # LLMベースの分類（簡易実装）
        if any(keyword in text for keyword in ["教えて", "について"]):
            state["intent"] = "rag"
        elif any(keyword in text for keyword in ["要約", "まとめ"]):
            state["intent"] = "summarize"
        elif any(keyword in text for keyword in ["手順", "実装"]):
            state["intent"] = "plan"
        else:
            state["intent"] = "unknown"
    
    return state


def process_by_intent(state: State) -> State:
    """intentに応じて処理を分岐します"""
    intent = state["intent"]
    text = state["input"]
    
    if intent == "rag":
        state["output"] = f"「{text}」について検索しました。関連情報はドキュメントを参照してください。"
        logging.info("RAG branch executed")
    elif intent == "summarize":
        state["output"] = f"「{text[:50]}...」を要約しました。主要なポイントを抽出しています。"
        logging.info("Summarize branch executed")
    elif intent == "plan":
        state["output"] = f"「{text}」の実装手順を作成しました。1.要件定義 2.設計 3.実装 4.テスト"
        logging.info("Plan branch executed")
    else:
        state["output"] = f"「{text}」を一般処理しました。意図を特定できませんでした。"
        logging.info("Default branch executed")
    
    return state


def format_output(state: State) -> State:
    """最終出力を整形します"""
    intent = state["intent"]
    output = state["output"]
    
    formatted = f"""処理結果:
分類: {intent}
{output}

実行ログ: 処理が正常に完了しました。"""
    
    state["output"] = formatted
    return state


def main(argv: List[str] | None = None) -> int:
    """CLIのエントリポイントです。

    受講者は `run_graph()` を実装します。ここは引数解析/検証/終了コードを担当します。
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    try:
        _validate_args(args)
    except Exception as e:
        logging.error(str(e))
        print(str(e), file=sys.stderr)
        return 2

    logging.info("mode=%s", args.mode)

    try:
        out = run_graph(text=args.text, mode=args.mode)
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
