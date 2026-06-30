from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, ReadTimeoutError


def build_parser() -> argparse.ArgumentParser:
    """Day04のCLI引数を定義します（ユーザー入力テキスト）。"""
    p = argparse.ArgumentParser(prog="day04")
    p.add_argument("--text", required=True)
    return p


def _validate_args(args: argparse.Namespace) -> None:
    """引数の簡易バリデーションを行います（入力不備は exit code=2）。"""
    if not args.text:
        raise ValueError("--text is required")


def tool_today() -> str:
    """今日の日付をYYYY-MM-DD形式で返すツール"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        logging.info(f"Tool 'today' called: returning {today}")
        return today
    except Exception as e:
        logging.error(f"Tool 'today' failed: {e}")
        raise Exception(f"Failed to get today's date: {e}")


def _call_bedrock_with_tools(prompt: str, tools: List[Dict[str, Any]]) -> str:
    """Bedrockをツール呼び出し機能付きで呼び出す"""
    try:
        # Bedrock Runtimeクライアントを作成
        config = Config(
            read_timeout=30,
            connect_timeout=30,
            retries={'max_attempts': 0}
        )
        client = boto3.client('bedrock-runtime', region_name='ap-northeast-1', config=config)
        
        # ツール呼び出しを含むプロンプトを作成
        system_prompt = """あなたはAIアシスタントです。ユーザーの質問に答える際、必要に応じて以下のツールを使用してください。

利用可能なツール:
- today: 今日の日付をYYYY-MM-DD形式で取得します。引数は不要です。

ツール使用ルール:
- 日付に関する質問にはtodayツールを使用してください
- ツール呼び出しはXML形式で行ってください
- ツール結果を元に、自然な日本語で回答してください

ツール呼び出し形式:
<invoke>
<tool_name>ツール名</tool_name>
<parameters>
</parameters>
</invoke>"""
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Bedrock呼び出し
        response = client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(request_body)
        )
        
        # レスポンスから回答本文を抽出
        response_body = response.get('body').read()
        response_data = json.loads(response_body)
        
        if 'content' in response_data and len(response_data['content']) > 0:
            return response_data['content'][0]['text']
        else:
            raise ValueError("No content in Claude response")
            
    except NoCredentialsError:
        raise Exception("AWS認証情報が見つかりません。~/.aws/credentialsを確認してください。")
    except PartialCredentialsError:
        raise Exception("AWS認証情報が不完全です。アクセスキーとシークレットキーを確認してください。")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            raise Exception(f"Bedrockへのアクセス権限がありません。IAMポリシーを確認してください: {e.response['Error']['Message']}")
        else:
            raise Exception(f"Bedrock呼び出しエラー ({error_code}): {e.response['Error']['Message']}")
    except ReadTimeoutError:
        raise Exception("Bedrock呼び出しがタイムアウトしました。ネットワーク接続を確認してください。")
    except Exception as e:
        if "timeout" in str(e).lower():
            raise Exception(f"タイムアウトが発生しました: {str(e)}")
        else:
            raise Exception(f"予期せぬエラーが発生しました: {str(e)}")


def _process_tool_calls(response: str) -> str:
    """レスポンス内のツール呼び出しを処理する"""
    # 簡単なXMLパースでツール呼び出しを検出
    if "<invoke>" in response and "</invoke>" in response:
        logging.info("Tool call detected in response")
        
        # todayツール呼び出しを検出
        if "<tool_name>today</tool_name>" in response:
            logging.info("Calling 'today' tool")
            result = tool_today()
            
            # ツール結果を含む最終プロンプトを作成
            final_prompt = f"""前の応答でtodayツールを呼び出しました。

ツール実行結果:
{result}

この結果を元に、元のユーザー質問に自然な日本語で答えてください。"""
            
            # ツール結果を元に再度呼び出し
            return _call_bedrock_with_tools(final_prompt, [])
    
    return response


def run_chain(text: str) -> str:
    """LangChain + Tool calling を使って回答（文字列）を返します。

    この関数を実装すると、`python -m day04.app --text ...` が動くようになります。

    要件（READMEの受け入れ基準）：
    - `today` または `add` のツールを1つ実装し、LLMから1回以上呼び出す
    - ツール引数のバリデーションを入れる（不正なら実行しない）
    - ツール失敗時は安全に失敗する（例外でOK。mainがexit code=1にする）

    ヒント：
    - まずはツールをPython関数として作り、ログで「呼ばれた」ことを確認
    - 次にLLM側のプロンプトで「必要ならツールを使う」よう誘導
    """
    try:
        # 最初の呼び出し
        initial_response = _call_bedrock_with_tools(text, [])
        logging.info(f"Initial response: {initial_response[:100]}...")
        
        # ツール呼び出しを処理
        final_response = _process_tool_calls(initial_response)
        
        # ツールが呼ばれたかログで確認
        if "Tool 'today' called" in str(logging.getLogger().handlers):
            logging.info("Tool was successfully called during execution")
        
        return final_response
        
    except Exception as e:
        logging.error(f"run_chain failed: {e}")
        raise


def main(argv: List[str] | None = None) -> int:
    """CLIのエントリポイントです。

    受講者は `run_chain()` の実装に集中し、ここは原則編集しません。
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _validate_args(args)
    except Exception as e:
        logging.error(str(e))
        print(str(e), file=sys.stderr)
        return 2

    try:
        out = run_chain(args.text)
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
