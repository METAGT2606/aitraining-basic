from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, ReadTimeoutError
from dotenv import load_dotenv


def build_parser() -> argparse.ArgumentParser:
    """Day02のCLI引数を定義します（READMEの機能要件に対応）。"""
    p = argparse.ArgumentParser(prog="day02")
    p.add_argument("--prompt", required=True)
    p.add_argument("--region", default=None)
    p.add_argument("--model-id", default=None)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--timeout-sec", type=int, default=30)
    return p


def _validate_args(args: argparse.Namespace) -> None:
    """引数の簡易バリデーションを行います（入力不備は exit code=2）。"""
    if not args.prompt:
        raise ValueError("--prompt is required")
    if not (0.0 <= args.temperature <= 1.0):
        raise ValueError("--temperature must be between 0.0 and 1.0")
    if args.max_tokens <= 0:
        raise ValueError("--max-tokens must be a positive integer")
    if args.timeout_sec <= 0:
        raise ValueError("--timeout-sec must be a positive integer")


def invoke_bedrock(
    *,
    prompt: str,
    region: str,
    model_id: str,
    temperature: float,
    max_tokens: int,
    timeout_sec: int,
) -> str:
    """Bedrockを呼び出して回答本文（文字列）を返します。

    この関数を実装すると、`python -m day02.app ...` が動くようになります。

    実装ガイド：
    - boto3のBedrock Runtimeクライアントを作る（リージョンは `region` を使う）
    - `model_id` で指定されたモデルを呼び出す
    - `temperature` / `max_tokens` をリクエストに反映する
    - `timeout_sec` はHTTPクライアント設定やタイムアウト制御に反映する
    - 返すのは「回答本文のみ」（前後に装飾文を混ぜない）

    エラー時：
    - 認証/権限/ネットワーク/タイムアウトなどは例外として投げてOK
     （main側で終了コード=1にしてstderrへ出ます）
    """
    try:
        # Bedrock Runtimeクライアントを作成（タイムアウト設定を反映）
        config = Config(
            read_timeout=timeout_sec,
            connect_timeout=timeout_sec,
            retries={'max_attempts': 0}  # リトライは無効化（タイムアウト制御のため）
        )
        client = boto3.client('bedrock-runtime', region_name=region, config=config)
        
        # モデルに応じたリクエストボディを作成
        if model_id.startswith('anthropic.claude'):
            # Claudeモデルの場合
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        elif model_id.startswith('amazon.titan'):
            # Titanモデルの場合
            request_body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                    "stopSequences": []
                }
            }
        else:
            # その他のモデル（汎用フォーマット）
            request_body = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        
        # Bedrock呼び出し
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        # レスポンスから回答本文を抽出
        response_body = response.get('body').read()
        response_data = json.loads(response_body)
        
        if model_id.startswith('anthropic.claude'):
            # Claudeのレスポンス形式
            if 'content' in response_data and len(response_data['content']) > 0:
                return response_data['content'][0]['text']
            else:
                raise ValueError("No content in Claude response")
        elif model_id.startswith('amazon.titan'):
            # Titanのレスポンス形式
            if 'results' in response_data and len(response_data['results']) > 0:
                return response_data['results'][0]['outputText']
            else:
                raise ValueError("No results in Titan response")
        else:
            # その他のモデルの場合
            if 'text' in response_data:
                return response_data['text']
            elif 'completion' in response_data:
                return response_data['completion']
            else:
                raise ValueError(f"Unexpected response format for model {model_id}")
                
    except NoCredentialsError:
        raise Exception("AWS認証情報が見つかりません。~/.aws/credentialsを確認してください。")
    except PartialCredentialsError:
        raise Exception("AWS認証情報が不完全です。アクセスキーとシークレットキーを確認してください。")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            raise Exception(f"Bedrockへのアクセス権限がありません。IAMポリシーを確認してください: {e.response['Error']['Message']}")
        elif error_code == 'ValidationException':
            raise Exception(f"リクエストパラメータが無効です: {e.response['Error']['Message']}")
        elif error_code == 'ModelTimeoutException':
            raise Exception(f"モデルがタイムアウトしました。リクエストを再試行してください: {e.response['Error']['Message']}")
        elif error_code == 'ModelNotReadyException':
            raise Exception(f"モデルが準備できていません: {e.response['Error']['Message']}")
        else:
            raise Exception(f"Bedrock呼び出しエラー ({error_code}): {e.response['Error']['Message']}")
    except ReadTimeoutError:
        raise Exception(f"Bedrock呼び出しが{timeout_sec}秒でタイムアウトしました。ネットワーク接続を確認するか、timeout-secを増やしてください。")
    except Exception as e:
        if "timeout" in str(e).lower():
            raise Exception(f"タイムアウトが発生しました: {str(e)}")
        else:
            raise Exception(f"予期せぬエラーが発生しました: {str(e)}")


def main(argv: List[str] | None = None) -> int:
    """CLIのエントリポイントです。

    受講者は原則 `invoke_bedrock()` のみ実装し、それ以外は触らない想定です。
    """
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _validate_args(args)
    except Exception as e:
        logging.error(str(e))
        print(str(e), file=sys.stderr)
        return 2

    region: Optional[str] = args.region or os.getenv("AWS_REGION")
    model_id: Optional[str] = args.model_id or os.getenv("BEDROCK_MODEL_ID")

    if not region:
        msg = "region is required: set --region or AWS_REGION"
        logging.error(msg)
        print(msg, file=sys.stderr)
        return 2

    if not model_id:
        msg = "model-id is required: set --model-id or BEDROCK_MODEL_ID"
        logging.error(msg)
        print(msg, file=sys.stderr)
        return 2

    logging.info(
        "region=%s model-id=%s temperature=%s max-tokens=%s timeout-sec=%s",
        region,
        model_id,
        args.temperature,
        args.max_tokens,
        args.timeout_sec,
    )

    try:
        reply = invoke_bedrock(
            prompt=args.prompt,
            region=region,
            model_id=model_id,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_sec=args.timeout_sec,
        )
        print(reply)
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
