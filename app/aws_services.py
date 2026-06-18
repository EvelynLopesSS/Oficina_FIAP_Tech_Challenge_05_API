import os
import boto3
import json

s3_client = boto3.client('s3', region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
sqs_client = boto3.client('sqs', region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
QUEUE_URL = os.getenv("SQS_QUEUE_URL")

def upload_video_to_s3(file_obj, filename):
    s3_key = f"uploads/{filename}"
    s3_client.upload_fileobj(file_obj, BUCKET_NAME, s3_key)
    return s3_key

def send_to_sqs(video_id, s3_video_key, user_email):
    mensagem = {
        "video_id": video_id,
        "s3_video_key": s3_video_key,
        "user_email": user_email
    }
    sqs_client.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(mensagem)
    )

def generate_presigned_url(s3_zip_key):
    # Gera uma URL temporária (1 hora) para o usuário baixar o ZIP direto do S3 com segurança
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': s3_zip_key},
        ExpiresIn=3600
    )
    return url