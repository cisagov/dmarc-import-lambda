import json
import logging
import os

from boto3 import client as boto3_client

from dmarc import s3

# This Lambda function expects the following environment variables to be
# defined:
# 1. queue_url - The url of the SQS queue containing the events to be
# processed
# 2. elasticsearch_url - A URL corresponding to an AWS Elasticsearch
# instance, including the index where the DMARC aggregate reports
# should be written
# 3. elasticsearch_region - The AWS region where the Elasticsearch
# instance is located

# The file where any domains identified from the DMARC aggregate reports should
# be saved.
DOMAINS = None

# The file where DMARC aggregate reports should be saved.
REPORTS = None

# Whether or not to delete the objects from the S3 bucket once they are
# successfully processed
DELETE = True

# The XSD file against which the DMARC aggregate reports are to be be verified
SCHEMA = 'dmarc/rua_mod.xsd'

# The Dmarcian API token
TOKEN = None

# In the case of AWS Lambda, the root logger is used BEFORE our Lambda handler
# runs, and this creates a default handler that goes to the console.  Once
# logging has been configured, calling logging.basicConfig() has no effect.  We
# can get around this by removing any root handlers (if present) before calling
# logging.basicConfig().  This unconfigures logging and allows --debug to
# affect the logging level that appears in the CloudWatch logs.
#
# See
# https://stackoverflow.com/questions/1943747/python-logging-before-you-run-logging-basicconfig
# and
# https://stackoverflow.com/questions/37703609/using-python-logging-with-aws-lambda
# for more details.
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

        # Set up logging
        log_level = logging.DEBUG
        logging.basicConfig(format='%(asctime)-15s %(levelname)s %(message)s',
                            level=log_level)

# Boto3 clients for SQS, S3, and Lambda.  We make these static so they can be
# reused if the Lambda function is called again on the same host.
sqs_client = boto3_client('sqs')
s3_client = boto3_client('s3')
lambda_client = boto3_client('lambda')


def handler(event, context):
    """
    Handler for all Lambda events
    """
    logging.info('AWS Event was: {}'.format(event))

    if 'source' in event and event['source'] == 'aws.events':
        # This is a scheduled event.  See
        # https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/EventTypes.html#schedule_event_type
        # for an example of what these events look like.

        # Launch a bunch of other lambdas to process events in the SQS queue
        while True:
            response = sqs_client.receive_message(QueueUrl=os.environ['queue_url'],  # noqa: E501
                                                  MaxNumberOfMessages=10,
                                                  VisibilityTimeout=330)
            for message in response['Messages']:
                logging.debug('Message from queue is {}'.format(message))
                lambda_client.invoke(FunctionName=os.environ['AWS_LAMBDA_FUNCTION_NAME'],  # noqa: E501
                                     InvocationType='Event',
                                     Payload=json.dumps(message))
    else:
        # This is an SQS message relayed by the parent Lambda function.
        #
        # Extract some variables from the event dictionary.  See
        # https://docs.aws.amazon.com/AmazonS3/latest/dev/notification-content-structure.html
        # for details on the event structure corresponding to objects created
        # in an S3 bucket.
        receipt_handle = event['ReceiptHandle']
        body = json.loads(event['Body'])
        success = {}
        for record in body['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']

            # Process the DMARC aggregate reports
            returnVal = s3.do_it(SCHEMA, bucket, key,
                                 DOMAINS, REPORTS,
                                 os.environ['elasticsearch_url'],
                                 os.environ['elasticsearch_region'],
                                 TOKEN, DELETE)
            logging.debug('Response from do_it() is {}'.format(returnVal))

            # Update the success dictionary
            success = {**success, **returnVal}

        # If everything succeeded then delete the message from the queue
        if all(v for v in success.values()):
            logging.info('Deleting message from queue after '
                         'successful processing')
            sqs_client.delete_message(QueueUrl=os.environ['queue_url'],
                                      ReceiptHandle=receipt_handle)
