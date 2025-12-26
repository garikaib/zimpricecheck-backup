import boto3
from botocore.config import Config

session = boto3.Session(
    aws_access_key_id='31wz69RYZEDaF1pKnIE7',
    aws_secret_access_key='n2SCWbvV8FYlKwynyV4FSxRS9Nnr7sHeoVA17Ez5'
)

s3 = session.client(
    's3',
    endpoint_url='https://t5k4.ldn.idrivee2-61.com',
    region_name='eu-west-3',
    config=Config(signature_version='s3v4')
)

try:
    response = s3.list_buckets()
    print("Buckets:")
    for bucket in response['Buckets']:
        print(f"- {bucket['Name']}")
except Exception as e:
    print(f"Error: {e}")
