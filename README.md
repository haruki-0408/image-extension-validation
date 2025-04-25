# デプロイ手順(SAM使えばよかった。。。)

## 1. 依存環境のインストール
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
## 2. ディレクトリ構成例

.
├── main.py
├── requirements.txt
├── venv/             
└── lambda.zip     # 作成されるZIPファイル

## 3. ZIP化
```bash
mkdir package
cp main.py package/
pip install -r requirements.txt -t package/
cd package
zip -r ../lambda.zip .
cd ..
```

## 4. IAMロール作成（初回のみ）

```bash
# トラストポリシーを直接渡してロール作成
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

```bash
# CloudWatch Logs 書き込み用ポリシーをアタッチ
aws iam attach-role-policy \
  --role-name image-extension-validation-function-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# S3からファイルを読み込むためのポリシーをアタッチ
aws iam attach-role-policy \
  --role-name image-extension-validation-function-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```


## 5. Lambda関数のアップロード or 更新

# 新規作成（初回）
```bash
aws lambda create-function \
  --function-name image-extension-validaton-function \
  --runtime python3.12 \
  --role {ロールのARN} \
  --handler main.lambda_handler \
  --zip-file fileb://lambda.zip
```

# 関数の更新（2回目以降→毎回zip化後）
```bash
aws lambda update-function-code \
  --function-name image-extension-validaton-function \
  --zip-file fileb://lambda.zip
```