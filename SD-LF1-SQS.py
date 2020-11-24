import json
import base64
import boto3

def lambda_handler(event, context):
    # Auth
    ACCESS_KEY = ''
    SECRET_KEY = ''
    REGION = ''

    # Initial
    FaceDetected = False

    # Fetch KDS data
    print(event)
    for record in event['Records']:
        if FaceDetected is True:
            break
        data_raw = record['kinesis']['data']
        data_str = base64.b64decode(data_raw).decode('ASCII')
        data = json.loads(data_str)
        print(data)
        if len(data['FaceSearchResponse']) > 0:
            FaceDetected = True
            sqs = boto3.resource('sqs',
                                 aws_access_key_id=ACCESS_KEY,
                                 aws_secret_access_key=SECRET_KEY,
                                 region_name=REGION
                                 )
            queue = sqs.get_queue_by_name(QueueName='Faces')
            data = json.dumps(data)
            send_msg = queue.send_message(MessageBody=data)
            print("Face detected and data sent to SQS")
        else:
            continue