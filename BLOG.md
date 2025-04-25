## はじめに
みなさんこんにちは、今回はs3に関する小ネタです。
s3コンソール画面のタイプ表示やそれに付随するメタデータのContent-Typeはファイルの拡張子しか見ていません。

※バケット名がimabe(imageの入力ミス)となっているのは許してください。


さらに言えば以下のバケットポリシーでjpg以外の拡張子のアップロードを明示的に禁止して見ると、当然ですが拡張子「.png」などはアップロードできません


```
{
    "Version": "2012-10-17",
    "Id": "AllowOnlyJpgUpload",
    "Statement": [
        {
            "Sid": "DenyNonJpgUpload",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:PutObject",
            "NotResource": "arn:aws:s3:::{バケット名}/*.jpg"
        }
    ]
}
```





しかし、拡張子さえ変えれば実際のデータは「png」や「mp4」なのにアップロードできてしまうわけです。



拡張子はあくまで人間が判断できるように存在しておりシステム的な制限やプロトコルで使用する場合は「MIME-Type」やバイナリで確認できるファイル識別子に関する「マジックナンバー」で判定した方が良いです。

マジックナンバーについて↓

https://cybersecurity-jp.com/security-words/99558#:~:text=JPEG%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB%EF%BC%9A%E5%85%88%E9%A0%AD%E3%83%90%E3%82%A4%E3%83%88%E3%81%8C,%E3%81%82%E3%82%8B%E3%81%93%E3%81%A8%E3%82%92%E7%A4%BA%E3%81%97%E3%81%BE%E3%81%99%E3%80%82

http://qiita.com/forestsource/items/15933888466ba9c3f048

**注意! ここでの「マジックナンバー」は**
本記事で使用している 「マジックナンバー」 という言葉は、**プログラミング一般で使われる「ハードコーディングされた一見意味のわからない定数」**のことではありません。
今回はファイルの先頭に配置されている固定のバイナリパターンを指します。

そこで今回はファイル識別子に関するマジックナンバーの仕組みを使って拡張子ではない本当のファイルタイプを判別してくれる様に以下のフローで検知してみます。

```
S3オブジェクトアップロード → 「.jpg」のみイベント通知 → Lambda関数でマジックナンバーを使用しmimeTypeを判定 → 本当に「jpg」かどうか確かめる
```
今回はあくまで確かめるだけです。その後の展開として通知を送信したり、禁止ファイルを削除したり等の処理が期待されます。

## Lambda用IAMロールの作成
まず、Lambda用のIAMロールを作成します。
```bash
aws iam create-role \
  --role-name image-extension-validation-function-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "lambda.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }'
```

- CloudWatch Logs 書き込み用ポリシーをアタッチ
- S3からファイルを読み込むためのポリシーをアタッチ
```bash
aws iam attach-role-policy \
  --role-name image-extension-validation-function-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole


aws iam attach-role-policy \
  --role-name image-extension-validation-function-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

## Lambda関数の用意

### 環境

| 項目           | 設定値                             |
|----------------|------------------------------------|
| ランタイム     | Python 3.12                        |
| ハンドラー     | `main.lambda_handler`              |
| タイムアウト   | 3〜10秒（推奨）                    |
| メモリ設定     | 128〜256MB                         |
| トリガー       | S3イベント通知（ObjectCreated:Put）|
| 層（Layer）    | なし                               |

---

### 使用ライブラリ

| ライブラリ名 | 用途                     |
|--------------|--------------------------|
| `boto3`      | S3とのやりとり（get/delete） |
| `python-majic`| バイナリデータ処理（必要に応じて） |


---
「python-magic」はfileコマンド等で使われている「libmagic」というC言語ライブラリのラッパーで、パターン定義済みのマジックファイルと読み込んだバイナリの先頭バイトを照らし合わせてMIMEタイプを判定してくれるライブラリです。今回はこちらを使ってS3にアップロードされた本当のファイルタイプを検知していきます。

https://pypi.org/project/python-magic/

https://github.com/ahupp/python-magic

まずは検知に使用するLambda関数を用意します。検証用の簡易的な関数の用意方法は色々あると思いますが、
今回はシンプルにローカルでファイル作成→依存関係もろともパッケージ化(zip)→アップロードという手順で作成してみたいと思います。依存関係やファイルが増えてくるとSAMなど使うと便利ですね。

```python
import boto3
import magic
import urllib.parse

s3 = boto3.client('s3')

def lambda_handler(event, context):
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(record['s3']['object']['key'])

    obj = s3.get_object(Bucket=bucket, Key=key)
    
    body = obj['Body'].read(1024)
    mime = magic.from_buffer(body, mime=True)
    print(f"[ファイル] {key} の実際のMIMEタイプ: {mime}")

    if key.endswith('.jpg') and mime != 'image/jpeg':
        print(f"警告: {key} はJPEGではありません！（実際: {mime}）")

```

今回はS3イベント通知を使うので、以下のJSON形式でイベント通知が期待されます。

https://docs.aws.amazon.com/ja_jp/AmazonS3/latest/userguide/notification-content-structure.html

```
body = obj['Body'].read(1024)
mime = magic.from_buffer(body, mime=True)
```
この箇所でオブジェクトの先頭1kBの部分のみを読み取り、magic.from_buffer関数にてマジックナンバーからmimeTypeを返してもらい判定しています。

## S3イベント通知設定
