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
