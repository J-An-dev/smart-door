import json
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import time


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


def lambda_handler(event, context):
    print(event)
    body = json.loads(event)
    print(body)

    validation_result = validate(body)
    print(f"validate_body: {validation_result}")
    if validation_result["isValid"]:
        otp = body["otp"]  # get OTP from URL
        faceId = body["faceId"]  # get faceId from URL

        print(f"OTP: {otp}")
        print(f"faceId: {faceId}")

        try:
            status_validation = validate_user_otp(otp, faceId)
            print(f"validate_user_otp: {status_validation}")

            if status_validation == "correct":
                # Fetch name from DynamoDB using phone as key
                name = authorise_user(faceId)

                body = {
                    "message": f"Visitor {name} is now authorized.",
                    "name": name
                }

            elif status_validation == "used":
                body = {
                    "message": "This OTP is already used once. Please show up in front of the camera to request a new one."
                }

            else:
                body = {
                    "message": "Wrong OTP. Access denied!"
                }

            response = build_response(200, body)
            print(response)
            return response

        except ClientError as e:
            print("ClientError:")
            print(e.response['Error']['Message'])

            if not otp or not faceId:
                return build_response(500, {"message": "Error parsing the link"})

    else:
        response = build_response(
            500, {"message": validation_result["message"]})
        print(response)
        return response


def validate(body):
    if not body:
        return build_validation_result(
            False,
            'body',
            'There is no body in the event.'
        )
    otp = body.get("otp", None)
    if not otp:
        return build_validation_result(
            False,
            'otp',
            'There is no OTP in the body.'
        )

    if not isvalid_otp(otp):
        return build_validation_result(
            False,
            'otp',
            'The OTP is invalid.'
        )
    return {'isValid': True}


# Visitor OTP Validation
def isvalid_otp(otp):
    if len(otp) != 6:
        return False
    return True


# Validate OTP via DynamoDB
def validate_user_otp(otp, faceId):
    currentTime = int(time.time())
    response = passcodesTable.query(KeyConditionExpression=Key('faceId').eq(
        faceId), FilterExpression=Key('ttl').gt(currentTime)&Key('passcode').eq(int(otp)))
    print(response)
    if response['Count'] == 1:
        if response['Items'][0]['used'] == False:
            expire_otp = passcodesTable.update_item(
                Key={'faceId': faceId},
                UpdateExpression="set used =:i",
                ExpressionAttributeValues={":i": True},
                ReturnValues="UPDATED_NEW"
            )
            return "correct"  # OTP matches with DB OTP
        else:
            return "used"  # OTP is already used once
    return False  # OTP doesn't match with DB OTP


# Grant visitor access through the SmartDoor
def authorise_user(faceId):
    response = visitorsTable.query(
        KeyConditionExpression=Key('faceId').eq(faceId))
    # Return name of the user from DB using faceId
    name = response['Items'][0]['name']
    print(f"name: {name}")
    return name


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