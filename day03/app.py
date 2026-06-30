from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Dict, List

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, ReadTimeoutError
from dotenv import load_dotenv


def build_parser() -> argparse.ArgumentParser:
    """Day03のCLI引数を定義します（要件文とリトライ回数）。"""
    p = argparse.ArgumentParser(prog="day03")
    p.add_argument("--requirements", required=True)
    p.add_argument("--max-retry", type=int, default=1)
    return p


def _validate_args(args: argparse.Namespace) -> None:
    """引数の簡易バリデーションを行います（入力不備は exit code=2）。"""
    if not args.requirements:
        raise ValueError("--requirements is required")
    if not (0 <= args.max_retry <= 3):
        raise ValueError("--max-retry must be between 0 and 3")


def generate_json(requirements: str) -> str:
    """要件文字列から、JSON文字列（本文のみ）を生成して返します。

    この関数を実装すると、`python -m day03.app --requirements ...` が動くようになります。

    実装ガイド：
    - LLMに「JSONだけを返す」ように強く指示する
    - `title` / `tasks` / `risks` を必ず含める
    - `tasks` は配列で、各要素に `id` / `description` / `acceptance_criteria` を含める
    - 返す文字列は JSON として `json.loads()` できる必要がある

    注意：
    - 余計な前置き/後置きの文章を混ぜない
    - 壊れやすいので、プロンプトは短く・形式を固定する
    """
    try:
        # Bedrock Runtimeクライアントを作成
        config = Config(
            read_timeout=30,
            connect_timeout=30,
            retries={'max_attempts': 0}
        )
        client = boto3.client('bedrock-runtime', region_name='ap-northeast-1', config=config)
        
        # JSON出力を強制するプロンプトを作成
        prompt = f"""以下の要件からタスク分解を行い、指定されたJSON形式で出力してください。

要件: {requirements}

出力形式（JSONのみ、他の文章を含めない）:
{{
  "title": "要件の要約タイトル",
  "tasks": [
    {{
      "id": 1,
      "description": "具体的な作業内容",
      "acceptance_criteria": "完了条件"
    }},
    {{
      "id": 2,
      "description": "具体的な作業内容",
      "acceptance_criteria": "完了条件"
    }}
  ],
  "risks": ["想定されるリスク1", "想定されるリスク2"]
}}

注意:
- JSON形式のみ出力し、前置きや説明文を一切含めない
- tasksは少なくとも2つ以上含める
- すべての必須キー（title, tasks, risks）を含める"""
        
        # Claudeモデルを使用してJSON生成
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.2,
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
            generated_text = response_data['content'][0]['text']
            
            # 余計なテキストを除去して純粋なJSONのみを抽出
            generated_text = generated_text.strip()
            
            # JSONブロックを抽出（```jsonで囲まれている場合）
            if generated_text.startswith('```json'):
                generated_text = generated_text[7:]
            if generated_text.endswith('```'):
                generated_text = generated_text[:-3]
            generated_text = generated_text.strip()
            
            return generated_text
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


def validate_json(text: str) -> Dict[str, Any]:
    """生成結果のJSONを検証します（必須キーと型）。"""
    obj = json.loads(text)
    for key in ("title", "tasks", "risks"):
        if key not in obj:
            raise ValueError(f"missing key: {key}")
    if not isinstance(obj.get("tasks"), list):
        raise ValueError("tasks must be a list")
    return obj


def main(argv: List[str] | None = None) -> int:
    """CLIのエントリポイントです。

    JSON生成→検証→（失敗時は再生成）までを制御します。受講者は `generate_json()` を実装します。
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

    last_err: Exception | None = None
    for _ in range(args.max_retry + 1):
        try:
            text = generate_json(args.requirements)
            validate_json(text)
            print(text)
            return 0
        except NotImplementedError as e:
            logging.error(str(e))
            print(str(e), file=sys.stderr)
            return 1
        except Exception as e:
            last_err = e

    msg = str(last_err) if last_err else "validation failed"
    logging.error(msg)
    print(msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
