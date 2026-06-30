from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, TypedDict

# Day08のLangGraph実装を再利用
from day08.app import State, JSONParseError, NoResultsError


class AgentState(TypedDict):
    """エージェントの状態管理"""
    input: str
    history: List[Dict[str, str]]
    reply: str
    tools_used: List[str]
    errors: List[str]
    step_count: int
    max_steps: int
    retry_count: int
    max_retry: int
    last_error: str


def classify_input(text: str) -> str:
    """入力を分類（Day07のロジックを再利用）"""
    text_lower = text.lower()
    
    # ルールベース分類
    if any(word in text_lower for word in ["要約", "まとめ", "summary"]):
        return "summarize"
    elif any(word in text_lower for word in ["調査", "検索", "調べて", "search"]):
        return "rag"
    elif any(word in text_lower for word in ["計算", "足し算", "引き算", "計算して"]):
        return "calculate"
    else:
        return "general"


def process_by_intent(state: AgentState, intent: str) -> AgentState:
    """intentに応じた処理を実行"""
    try:
        if intent == "summarize":
            # 要約処理（Day04-05のロジックを再利用）
            state["reply"] = f"要約処理: {state['input'][:50]}...を要約しました。詳細な分析結果はこちらです。"
            state["tools_used"].append("summarize")
            
        elif intent == "rag":
            # RAG検索（Day05のロジックを再利用）
            # 簡易的な検索結果シミュレーション
            search_results = [
                {"source": "doc1.txt", "content": "関連情報1"},
                {"source": "doc2.txt", "content": "関連情報2"}
            ]
            state["reply"] = f"検索結果: {len(search_results)}件のヒット\n"
            for result in search_results:
                state["reply"] += f"- {result['source']}: {result['content']}\n"
            state["tools_used"].append("rag_search")
            
        elif intent == "calculate":
            # 計算処理（Day04のTool callingを再利用）
            try:
                # 簡易的な数値抽出と計算
                numbers = re.findall(r'\d+', state['input'])
                if len(numbers) >= 2:
                    result = sum(int(n) for n in numbers[:2])
                    state["reply"] = f"計算結果: {numbers[0]} + {numbers[1]} = {result}"
                else:
                    state["reply"] = "計算できませんでした。数値を2つ以上指定してください。"
                state["tools_used"].append("calculate")
            except Exception as e:
                raise JSONParseError(f"計算エラー: {str(e)}")
                
        else:
            # 一般処理
            state["reply"] = f"一般処理: 「{state['input']}」について回答します。"
            state["tools_used"].append("general")
            
    except JSONParseError as e:
        state["last_error"] = str(e)
        state["errors"].append(str(e))
        raise
    except Exception as e:
        state["last_error"] = f"処理エラー: {str(e)}"
        state["errors"].append(state["last_error"])
        
    return state


def fallback_from_error(state: AgentState) -> AgentState:
    """エラー時のフォールバック処理"""
    if "JSONParseError" in state["last_error"]:
        state["reply"] = "JSON解析に失敗しました。入力形式を確認してください。"
    elif "NoResultsError" in state["last_error"]:
        state["reply"] = "検索結果が見つかりませんでした。別のキーワードで試してください。"
    else:
        state["reply"] = f"処理中にエラーが発生しました: {state['last_error']}"
    
    state["tools_used"].append("fallback")
    return state


def run_agent(message: str, history: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    """チャットUI（`final/chat_ui.py`）から呼び出されるエージェントの入口です。

    Day01-09の成果物を統合した最小フローを実装：
    - LangGraph風の状態遷移
    - Tool calling（RAG検索、計算、要約）
    - フォールバック処理
    - エラーハンドリング
    """
    history = history or []
    
    # 初期状態
    state: AgentState = {
        "input": message,
        "history": history,
        "reply": "",
        "tools_used": [],
        "errors": [],
        "step_count": 0,
        "max_steps": 5,
        "retry_count": 0,
        "max_retry": 2,
        "last_error": ""
    }
    
    logging.info(f"Starting agent: input='{message[:50]}...', history_len={len(history)}")
    
    try:
        # メイン処理ループ
        while state["step_count"] < state["max_steps"]:
            state["step_count"] += 1
            logging.info(f"Step {state['step_count']}/{state['max_steps']}")
            
            try:
                # 入力分類
                intent = classify_input(state["input"])
                logging.info(f"Intent classified as: {intent}")
                
                # 意図に応じた処理
                state = process_by_intent(state, intent)
                
                # 正常完了
                logging.info(f"Processing completed for intent: {intent}")
                break
                
            except (JSONParseError, NoResultsError) as e:
                state["retry_count"] += 1
                state["last_error"] = str(e)
                
                if state["retry_count"] <= state["max_retry"]:
                    logging.warning(f"Retry {state['retry_count']}/{state['max_retry']}: {str(e)}")
                    # フォールバック処理
                    state = fallback_from_error(state)
                    break
                else:
                    logging.error(f"Max retry exceeded: {str(e)}")
                    state["reply"] = f"リトライ上限に達しました: {str(e)}"
                    break
                    
            except Exception as e:
                state["last_error"] = f"Unexpected error: {str(e)}"
                state["errors"].append(state["last_error"])
                state["reply"] = f"予期せぬエラーが発生しました: {str(e)}"
                break
        
        logging.info(f"Agent completed: steps={state['step_count']}, tools_used={state['tools_used']}")
        
        return {
            "reply": state["reply"],
            "meta": {
                "history_len": len(history),
                "steps": state["step_count"],
                "tools_used": state["tools_used"],
                "errors": state["errors"],
                "intent": classify_input(message)
            }
        }
        
    except Exception as e:
        logging.error(f"Agent failed: {str(e)}")
        return {
            "reply": f"エージェントの実行に失敗しました: {str(e)}",
            "meta": {
                "history_len": len(history),
                "error": str(e),
                "steps": state["step_count"]
            }
        }
