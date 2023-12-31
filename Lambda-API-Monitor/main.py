import requests
import boto3
import os
import json
from datetime import datetime
import time
import uuid

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')

# DynamoDB Table Name
table_name = 'APIResponsesTableNew'

###################### Some utility functions ############################################

def upload_logs_to_s3(logs, bucket_name, key):
    logs_str = json.dumps(logs, indent=2)
    s3.put_object(Body=logs_str, Bucket=bucket_name, Key=key)

def write_to_db(api_results, job_id):
    # Save API response data to DynamoDB
    put_requests = []
    timestamp = int(datetime.now().timestamp())
    for result in api_results:
        put_requests.append({
            'PutRequest': {
                'Item': {
                    'ID': {'S': result['_id']},
                    'Endpoint': {'S': result['endpoint']},
                    'Method': {'S': result['method']},
                    'StatusCode': {'N': str(result['status_code'])},
                    'IsSuccessful': {'BOOL': result['is_successful']},
                    'ResponseTime': {'N': str(result['response_time'])},
                    'ResponseHeaders': {'S': json.dumps(result['response_headers'])},
                    'ResponseBody': {'S': result['response_body']},
                    'JobID': {'S': job_id},
                    'Timestamp': {'N': str(timestamp)}
                }
            }
        })

    dynamodb.batch_write_item(
        RequestItems={
            table_name: put_requests
        }
    )


############### Monitor class to implement monitoring features ##############################

class MonitorAPI():
    def __init__(self):
        pass

    def test_api(self, method, endpoint, body=None):
        try:
            # Record start time
            start_time = datetime.now()

            # Make API request based on the method
            if method == 'GET':
                response = requests.get(endpoint)
            elif method == 'POST':
                response = requests.post(endpoint, json=body)
            elif method == 'DELETE':
                response = requests.delete(endpoint, json=body)
            else:
                raise ValueError(f'Invalid HTTP method: {method}')

            response_time = (datetime.now() - start_time).total_seconds()

            # Check if the response is successful (status code 2xx)
            is_successful = response.ok
            # Log API response details
            api_result = {
                '_id': str(uuid.uuid4()),
                'method': method,
                'endpoint': endpoint,
                'status_code': response.status_code,
                'is_successful': is_successful,
                'response_time': response_time,
                'response_headers': dict(response.headers),
                'response_body': response.text[:500]  # Limit response body length
            }
            return api_result
        
        except Exception as e:
            # Log if there's an exception during API request
            api_result = {
                '_id': str(uuid.uuid4()),
                'method': method,
                'endpoint': endpoint,
                'error': str(e)
            }
            return api_result

############### Actual Lambda Handler function ##############################
def handler(event, context):
    # Extract API tests from the event
    api_tests = event.get('API-Test')
    job_id = event.get('job_id')
    # Check if API tests are provided
    if not api_tests:
        return {
            'statusCode': 400,
            'body': 'Error: Missing API-Test in the event'
        }

    monitor = MonitorAPI()
    api_results = []

    for api_test in api_tests:
        endpoint = api_test.get('endpoint')
        method = api_test.get('method')
        body = api_test.get('body')

        if not (endpoint and method):
            return {
                'statusCode': 400,
                'body': f'Error: Missing endpoint/method in API test: {json.dumps(api_test)}'
            }

        try:
            # Test API endpoint
            result = monitor.test_api(method, endpoint, body)
            api_results.append(result)

        except Exception as e:
            # Log any unexpected exception
            error_message = f'Error during API monitoring: {str(e)}'
            return {
                'statusCode': 500,
                'body': error_message
            }

    # Upload API test results to S3
    timestamp = int(time.time() * 1000)
    key = f'API-Monitoring-logs-{timestamp}.json'
    upload_logs_to_s3(api_results, os.environ['S3_BUCKET_NAME'], key)

    # Write API response data to DynamoDB
    write_to_db(api_results, job_id)

    return {
        'statusCode': 200,
        'body': json.dumps(api_results),
        's3_key': key
    }
