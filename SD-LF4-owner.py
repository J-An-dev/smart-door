import json
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import time
import re
from random import randint


# Auth
ACCESS_KEY = ''
SECRET_KEY = ''
REGION = ''

# DynamoDB
dynamodb = boto3.resource('dynamodb',
                          aws_access_key_id=ACCESS_KEY,
                          aws_secret_access_key=SECRET_KEY,
                          region_name=REGION)
visitorsTable = dynamodb.Table('visitors')
passcodesTable = dynamodb.Table('passcodes')

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


def lambda_handler(event, context):
    print(event)
    body = json.loads(event)
    print(body)

    validation_result = validate(body)
    if validation_result["isValid"]:
        v_name = body["v_name"]
        v_phone = body["v_number"]
        v_phone = clean_phone(v_phone)
        v_phone = format_phone(v_phone)
        image_key = body["image_key"]
        print(f"Name: {v_name}")
        print(f"PhoneNumber: {v_phone}")
        print(f"Image Key: {image_key}")

        # Index the face and get the faceID
        faceId = index_face_and_get_faceId(bucketname, image_key, v_name)

        if not faceId:
            return build_response(500, {"message": {'contentType': 'PlainText', 'content': "No face detected"}})

        # Store into DynamoDB Tables
        store_into_visitors(faceId, image_key, v_name, v_phone)
        store_into_passcodes(faceId)
        res_body = {"message": f"Visitor {v_name} is now added to the database."}
        response = build_response(200, res_body)
    else:
        response = build_response(
            500, {"message": validation_result["message"]})

    return response


def validate(body):
    if not body:
        return build_validation_result(
            False,
            'body',
            'There is no body in the event'
        )
    v_name = body.get("v_name", None)
    v_phone = body.get("v_number", None)
    v_phone = clean_phone(v_phone)
    image_key = body.get("image_key", None)

    if not v_name:
        return build_validation_result(
            False,
            'v_name',
            'There is no name in the body'
        )
    if not v_phone:
        return build_validation_result(
            False,
            'v_number',
            'There is no phone number in the body'
        )
    if not isvalid_phone(v_phone):
        return build_validation_result(
            False,
            'v_number',
            'The phone number entered is invalid'
        )
    if not image_key:
        return build_validation_result(
            False,
            'image_key',
            'There is no image key in the body'
        )
    if not isvalid_image_key(image_key):
        return build_validation_result(
            False,
            'image_key',
            'The image key provided is invalid.'
        )
    return {'isValid': True}


def clean_phone(phone):
    phone = re.sub(r'[^0-9]', "", phone)
    if phone and phone[0] == '1':
        phone = phone[1:]
    return phone


def isvalid_phone(phone):
    if len(phone) != 10:
        return False
    return True


def format_phone(phone):
    us_prefix = "+1"
    return us_prefix + phone


def isvalid_image_key(image_key):
    try:
        search_image = s3.get_object(
            Bucket=bucketname,
            Key=image_key
        )
        print(search_image)
        return True
    except:
        return False


def store_into_visitors(faceId, image_key, v_name, v_phone):
    # image_key = 'kvs1_20201112-224107.jpeg'
    ymd, hms = image_key.split('.')[0].split('_')[1].split('-')
    createdTimestamp = f"{ymd[:4]}-{ymd[4:6]}-{ymd[-2:]}T{hms[:2]}:{hms[2:4]}:{hms[-2:]}"
    new_photo = [{"objectKey": image_key, "bucket": bucketname, "createdTimestamp": createdTimestamp}]
    upload_visiotr = visitorsTable.put_item(
        Item={
            "faceId": faceId,
            "name": v_name,
            "phoneNumber": v_phone,
            "photos": new_photo
        })
    print(upload_visiotr)


def store_into_passcodes(faceId):
    visitorsResponse = visitorsTable.query(KeyConditionExpression=Key('faceId').eq(faceId))
    print(visitorsResponse['Items'])
    if len(visitorsResponse['Items']) > 0:
        phone_number = visitorsResponse['Items'][0]['phoneNumber']
        name = visitorsResponse['Items'][0]['name']
        currentTime = int(time.time())
        print(currentTime)
        passcodesResponse = passcodesTable.query(KeyConditionExpression=Key('faceId').eq(faceId),
                                                 FilterExpression=Key('ttl').gt(currentTime))
        if len(passcodesResponse['Items']) > 0:
            otp = passcodesResponse['Items'][0]['passcode']
        else:
            otp = randint(10 ** 5, 10 ** 6 - 1)
            upload_new_otp = passcodesTable.put_item(
                Item={
                    "passcode": otp,
                    "faceId": faceId,
                    "ttl": int(time.time() + 5 * 60),
                    "used": False
                })
        access_link = f"https://{bucketname}.s3.amazonaws.com/static/html/wp2.html?faceId={faceId}"
        message = f"Welcome, {name}! Please click the link {access_link} to unlock the door. Your OTP is {otp} and it will expire in 5 minutes and can be only used once."
        sns.publish(
            PhoneNumber=phone_number,
            Message=message
        )
        print(f'Message "{message}" sent.')


def build_response(status_code, body):
    response = {}
    response["statusCode"] = status_code
    response["body"] = body
    response["headers"] = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,HEAD,OPTIONS,POST,PUT",
        "Access-Control-Allow-Headers": "Access-Control-Allow-Headers, Origin,Accept, X-Requested-With, Content-Type, Access-Control-Request-Method, Access-Control-Request-Headers"
    }
    print(f"Response: {response['body']}")
    return response


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': message_content
    }


def index_face_and_get_faceId(bucketname, image_key, v_name):
    rekognition = boto3.client("rekognition",
                               aws_access_key_id=ACCESS_KEY,
                               aws_secret_access_key=SECRET_KEY,
                               region_name=REGION)
    response = rekognition.index_faces(
        Image={
            "S3Object": {
                "Bucket": bucketname,
                "Name": image_key,
            }
        },
        CollectionId='FaceCollection',
        ExternalImageId=v_name,
        DetectionAttributes=['ALL'],
        MaxFaces=1,
        QualityFilter='AUTO'
    )
    face_records = response['FaceRecords']
    if face_records and len(face_records) > 0:
        return face_records[0]['Face']['FaceId']
    else:
        return None
