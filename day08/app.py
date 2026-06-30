from __future__ import annotations

import argparse
import logging
import sys
import json
import random
from typing import List, Dict, Any, TypedDict, Literal


class State(TypedDict):
    """LangGraphの状態を定義します"""
    input: str
    intent: Literal["rag", "summarize", "plan", "unknown"]
    output: str
    errors: List[str]
    step_count: int
    retry_count: int
    max_steps: int
    max_retry: int
    last_error: str


def build_parser() -> argparse.ArgumentParser:
    """Day08のCLI引数を定義します（入力と上限設定）。"""
    p = argparse.ArgumentParser(prog="day08")
    p.add_argument("--text", required=True)
    p.add_argument("--max-steps", type=int, default=10)
    p.add_argument("--max-retry", type=int, default=1)
    return p


def _validate_args(args: argparse.Namespace) -> None:
    """引数の簡易バリデーションを行います（入力不備は exit code=2）。"""
    if not args.text:
        raise ValueError("--text is required")
    if not (1 <= args.max_steps <= 50):
        raise ValueError("--max-steps must be between 1 and 50")
    if not (0 <= args.max_retry <= 5):
        raise ValueError("--max-retry must be between 0 and 5")


def run_graph(*, text: str, max_steps: int, max_retry: int) -> str:
    """失敗時復帰（リトライ/フォールバック）付きのフローを実行します。

    実装ガイド：
    - 失敗パターンを1つ以上作り、復帰パスへ入ることを確認する
      - 例：JSONが壊れる→再生成
      - 例：検索ヒットなし→聞き返し
    - `max_steps` / `max_retry` を上限として必ず反映し、無限ループを防ぐ
    - 上限到達時は明示的に失敗（例外）してよい（mainがexit code=1にする）
    """
    try:
        # 初期状態を設定
        state: State = {
            "input": text,
            "intent": "unknown",
            "output": "",
            "errors": [],
            "step_count": 0,
            "retry_count": 0,
            "max_steps": max_steps,
            "max_retry": max_retry,
            "last_error": ""
        }
        
        logging.info(f"Starting graph execution: max_steps={max_steps}, max_retry={max_retry}")
        
        # メインフロー実行
        while state["step_count"] < state["max_steps"]:
            state["step_count"] += 1
            logging.info(f"Step {state['step_count']}/{state['max_steps']}")
            
            try:
                # ノード1：入力を分類する
                state = classify_input(state)
                logging.info(f"Intent classified as: {state['intent']}")
                
                # ノード2：intentに応じて処理を分岐する（失敗可能性あり）
                state = process_by_intent(state)
                logging.info(f"Processing completed for intent: {state['intent']}")
                
                # ノード3：最終出力を整形する
                state = format_output(state)
                
                # 成功した場合
                logging.info("Graph execution completed successfully")
                return state["output"]
                
            except JSONParseError as e:
                logging.warning(f"JSON parse error: {e}")
                state["last_error"] = str(e)
                state["errors"].append(f"JSONパースエラー: {e}")
                
                # リトライ処理
                if state["retry_count"] < state["max_retry"]:
                    state["retry_count"] += 1
                    logging.info(f"Retrying... ({state['retry_count']}/{state['max_retry']})")
                    continue
                else:
                    # フォールバック処理
                    logging.info("Max retry reached, falling back...")
                    state = fallback_from_json_error(state)
                    break
                    
            except NoResultsError as e:
                logging.warning(f"No results error: {e}")
                state["last_error"] = str(e)
                state["errors"].append(f"検索結果なしエラー: {e}")
                
                # フォールバック処理
                logging.info("Falling back from no results...")
                state = fallback_from_no_results(state)
                break
                
        # 上限到達時
        if state["step_count"] >= state["max_steps"]:
            raise Exception(f"最大ステップ数（{state['max_steps']}）に到達しました")
        
        return state["output"]
        
    except Exception as e:
        logging.error(f"Graph execution failed: {e}")
        raise Exception(f"処理フローの実行に失敗しました: {e}")


class JSONParseError(Exception):
    """JSONパースエラー"""
    pass


class NoResultsError(Exception):
    """検索結果なしエラー"""
    pass


def classify_input(state: State) -> State:
    """入力を分類し、intentを決定します"""
    text = state["input"].lower()
    
    if any(keyword in text for keyword in ["教えて", "について", "とは"]):
        state["intent"] = "rag"
    elif any(keyword in text for keyword in ["要約", "まとめて", "要約して"]):
        state["intent"] = "summarize"
    elif any(keyword in text for keyword in ["手順", "方法", "実装", "やり方"]):
        state["intent"] = "plan"
    else:
        state["intent"] = "unknown"
    
    return state


def process_by_intent(state: State) -> State:
    """intentに応じて処理を分岐します（失敗可能性あり）"""
    intent = state["intent"]
    text = state["input"]
    
    # 人為的な失敗パターンを追加
    if "不完全なjson" in text.lower():
        raise JSONParseError("JSONの形式が不完全です")
    
    if "存在しない情報" in text.lower():
        raise NoResultsError("検索結果が見つかりませんでした")
    
    if intent == "rag":
        # 模擬的なJSONレスポンス（失敗可能性あり）
        if random.random() < 0.1:  # 10%の確率で失敗
            raise JSONParseError("レスポンスのJSONが壊れています")
        
        state["output"] = f"「{text}」について検索しました。関連情報が見つかりました。"
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


def fallback_from_json_error(state: State) -> State:
    """JSONエラーからのフォールバック処理"""
    logging.info("Applying fallback for JSON error")
    state["output"] = f"JSON処理に失敗したため、簡易応答を返します。「{state['input']}」について処理しました。"
    return state


def fallback_from_no_results(state: State) -> State:
    """検索結果なしからのフォールバック処理"""
    logging.info("Applying fallback for no results")
    state["output"] = f"検索結果がなかったため、一般的な情報を提供します。「{state['input']}」について、より具体的な質問をお願いします。"
    return state


def format_output(state: State) -> State:
    """最終出力を整形します"""
    intent = state["intent"]
    output = state["output"]
    step_count = state["step_count"]
    retry_count = state["retry_count"]
    
    formatted = f"""処理結果:
分類: {intent}
ステップ数: {step_count}
リトライ回数: {retry_count}
{output}

実行ログ: 処理が正常に完了しました。"""
    
    if state["errors"]:
        formatted += f"\n警告: {len(state['errors'])}件のエラーが発生しました"
    
    state["output"] = formatted
    return state


def main(argv: List[str] | None = None) -> int:
    """CLIのエントリポイントです。

    受講者は `run_graph()` を実装します。ここは引数解析/検証/上限の適用/終了コードを担当します。
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    try:
        _validate_args(args)
    except Exception as e:
        logging.error(str(e))
        print(str(e), file=sys.stderr)
        return 2

    logging.info("max-steps=%s max-retry=%s", args.max_steps, args.max_retry)

    try:
        out = run_graph(text=args.text, max_steps=args.max_steps, max_retry=args.max_retry)
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
