import json
import time
import boto3
import os
import cv2
from boto3.dynamodb.conditions import Key
from random import randint

def lambda_handler(event, context):
    # Auth
    ACCESS_KEY = ''
    SECRET_KEY = ''
    REGION = ''

    # S3
    s3 = boto3.client('s3',
                      aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY,
                      region_name=REGION)
    bucketname = 'smart-door-2020'

    # SNS
    sns = boto3.client('sns',
                       aws_access_key_id=ACCESS_KEY,
                       aws_secret_access_key=SECRET_KEY,
                       region_name=REGION)

    # DynamoDB
    dynamodb = boto3.resource('dynamodb',
                              aws_access_key_id=ACCESS_KEY,
                              aws_secret_access_key=SECRET_KEY,
                              region_name=REGION)
    visitorsTable = dynamodb.Table('visitors')
    passcodesTable = dynamodb.Table('passcodes')
    SNStrackingTable = dynamodb.Table('SNStracking')


    # SQS message will be automatically pulled and passed through event
    queue_body = event['Records'][0]['body']
    data = json.loads(queue_body)

    FaceResponse = data['FaceSearchResponse']
    FragmentNumber = data['InputInformation']['KinesisVideo']['FragmentNumber']


    # KVS video endpoint
    KinesisVideo = boto3.client('kinesisvideo',
                                aws_access_key_id=ACCESS_KEY,
                                aws_secret_access_key=SECRET_KEY,
                                region_name=REGION)
    endpoint = KinesisVideo.get_data_endpoint(APIName="GET_HLS_STREAMING_SESSION_URL", StreamName="KVS1")['DataEndpoint']

    # Grab the HLS stream URL from the endpoint
    KinesisVideoArchive = boto3.client('kinesis-video-archived-media',
                                       aws_access_key_id=ACCESS_KEY,
                                       aws_secret_access_key=SECRET_KEY,
                                       endpoint_url=endpoint)
    time.sleep(randint(1,5))  # to avoid exceeding the number of request for GetHLSStreamingSessionURL
    url = KinesisVideoArchive.get_hls_streaming_session_url(
            StreamName="KVS1",
            PlaybackMode="LIVE_REPLAY",
            HLSFragmentSelector={
                'FragmentSelectorType': 'PRODUCER_TIMESTAMP',
                'TimestampRange': {
                    'StartTimestamp': data['InputInformation']['KinesisVideo']['ProducerTimestamp']
                }
            }
    )['HLSStreamingSessionURL']

    # Retrieve the face image
    image_key = "kvs1_"
    video_cap = cv2.VideoCapture(url)
    # Pass the first 0.5s (video: 30fps)
    for i in range(15):
        ret, frame = video_cap.read()
    while True:
        # Capture frame-by-frame
        ret, frame = video_cap.read()
        if frame is not None:
            # Save the resulting frame
            createdTimestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            image_key = image_key + time.strftime("%Y%m%d-%H%M%S") + '.jpeg'
            cv2.imwrite('/tmp/' + image_key, frame)
            video_cap.release()
            break
        else:
            print("Frame is None")
            return {
                'statusCode': 500,
                'body': json.dumps('Something wrong with the video stream.')
            }
    # When everything done, release the capture
    video_cap.release()
    cv2.destroyAllWindows()

    for face in FaceResponse:
        if len(face['MatchedFaces']) > 0:
            faceId = face['MatchedFaces'][0]['Face']['FaceId']
            visitorsResponse = visitorsTable.query(KeyConditionExpression=Key('faceId').eq(faceId))
            phoneNumber = visitorsResponse['Items'][0]['phoneNumber']
            name = visitorsResponse['Items'][0]['name']
            photos = visitorsResponse['Items'][0]['photos']

            currentTime = int(time.time())
            passcodesResponse = passcodesTable.query(KeyConditionExpression=Key('faceId').eq(faceId),
                                                     FilterExpression=Key('ttl').gt(currentTime))
            if len(passcodesResponse['Items']) > 0:
                if passcodesResponse['Items'][0]['used'] == False:
                    # If the visitor visited in the past 5 minutes and hasn't used that OTP,
                    # then no need to generate a new one
                    otp = passcodesResponse['Items'][0]['passcode']
                    os.remove('/tmp/' + image_key)
                else:
                    # If the visitor visited in the past 5 minutes and has used that OTP,
                    # then generate a new one, but no need to append the new image
                    otp = randint(10 ** 5, 10 ** 6 - 1)
                    upload_new_otp = passcodesTable.put_item(
                        Item={
                            "passcode": otp,
                            "faceId": faceId,
                            "ttl": int(time.time() + 5 * 60),
                            "used": False
                        })
                    os.remove('/tmp/' + image_key)
            else:
                otp = randint(10**5, 10**6 - 1)
                upload_new_otp = passcodesTable.put_item(
                            Item={
                                "passcode": otp,
                                "faceId": faceId,
                                "ttl": int(time.time() + 5*60),
                                "used": False
                            })
                new_photo = {"objectKey": image_key, "bucket": bucketname, "createdTimestamp": createdTimestamp}
                photos.append(new_photo)
                update_visitorsTable = visitorsTable.update_item(
                    Key={'faceId': faceId},
                    UpdateExpression="set photos =:i",
                    ExpressionAttributeValues={":i": photos},
                    ReturnValues="UPDATED_NEW"
                )
                # Upload face image
                s3.upload_file('/tmp/' + image_key, bucketname, image_key)
                s3ImageLink = f"https://{bucketname}.s3.amazonaws.com/{image_key}"
                os.remove('/tmp/' + image_key)
                print(f"Known face image uploaded. Image link: {s3ImageLink}")

            # Send SMG to known visitor (no duplicate msg in 60s)
            time.sleep(2)
            currentTime = int(time.time())
            SNStracking = SNStrackingTable.query(KeyConditionExpression=Key('phoneNumber').eq(phoneNumber),
                                                     FilterExpression=Key('ttl').gt(currentTime))
            if len(SNStracking['Items']) == 0:
                upload_sns_ts = SNStrackingTable.put_item(
                            Item={
                                "phoneNumber": phoneNumber,
                                "ttl": int(time.time() + 60)
                            }
                )
                access_link = f"https://{bucketname}.s3.amazonaws.com/static/html/wp2.html?faceId={faceId}"
                message = f"Welcome, {name}! Please click the link {access_link} to unlock the door. Your OTP is {otp} and it will expire in 5 minutes and can be only used once."
                sns.publish(
                    PhoneNumber=phoneNumber,
                    Message=message
                )
                print(f'Message "{message}" sent.')
            else:
                print("Known visitor shows up. Would not like to bother you with duplicate msg.")

        # No matched face
        else:
            # Send SMG to owner (no duplicate msg in 60s)
            time.sleep(2)
            currentTime = int(time.time())
            SNStracking = SNStrackingTable.query(KeyConditionExpression=Key('phoneNumber').eq(''),
                                                 FilterExpression=Key('ttl').gt(currentTime))
            if len(SNStracking['Items']) == 0:
                # Upload face image
                s3.upload_file('/tmp/' + image_key, bucketname, image_key)
                s3ImageLink = f"https://{bucketname}.s3.amazonaws.com/{image_key}"
                os.remove('/tmp/' + image_key)
                print(f"Unknown face image uploaded. Image link: {s3ImageLink}")

                upload_sns_ts = SNStrackingTable.put_item(
                    Item={
                        "phoneNumber": "",
                        "ttl": int(time.time() + 60)
                    }
                )
                access_link = f"https://{bucketname}.s3.amazonaws.com/static/html/wp1.html?image={image_key}"
                message = f"Knock, kncok. An unknown visitor shows up. Please click the link {access_link} to approve or deny the access."
                sns.publish(
                    PhoneNumber="",
                    Message=message
                )
                print(f'Message "{message}" sent.')
            else:
                print("Unknown visitor shows up. Would not like to bother you with duplicate msg.")

    return {
        'statusCode': 200,
        'body': json.dumps('Mission Complete.')
    }