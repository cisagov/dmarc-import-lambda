import json
import logging

from boto3 import client as boto3_client
from boto3 import resource as boto3_resource

from dmarc import s3

# The file where any domains identified from the DMARC aggregate reports should
# be saved.
DOMAINS = None

# The file where DMARC aggregate reports should be saved.
REPORTS = None

# Whether or not to delete the objects from the S3 bucket once they are
# successfully processed
DELETE = False

# The name of the SQS queue containing the events to be processed
QUEUE_NAME = 'dmarc-import-queue'

# The name of this Lambda function
LAMBDA_FUNCTION_NAME = 'dmarc-import'


def handler(event, context):
    """
    Handler for all Lambda events
    """
    # In the case of AWS Lambda, the root logger is used BEFORE our Lambda
    # handler runs, and this creates a default handler that goes to the
    # console.  Once logging has been configured, calling logging.basicConfig()
    # has no effect.  We can get around this by removing any root handlers (if
    # present) before calling logging.basicConfig().  This unconfigures logging
    # and allows --debug to affect the logging level that appears in the
    # CloudWatch logs.
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
    logging.info('AWS Event was: {}'.format(event))

    if 'source' in event and event['source'] == 'aws.events':
        # This is a scheduled event.  See
        # https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/EventTypes.html#schedule_event_type
        # for an example of what these events look like.
        
        # Launch a bunch of other lambdas to process events in the SQS queue
        lambda_client = boto3_client('lambda')
        sqs_client = boto3_client('sqs')
        queue_url = sqs_client.get_queue_url(QueueName=QUEUE_NAME)['QueueUrl']
        response = sqs_client.receive_message(QueueUrl=queue_url,
                                              MaxNumberOfMessages=1,
                                              VisibilityTimeout=330)
        for message in response['Messages']:
            logging.debug('Message from queue is {}'.format(message))
            lambda_client.invoke(FunctionName=LAMBDA_FUNCTION_NAME,
                                 InvocationType='Event',
                                 Payload=json.dumps(message))
    else:
        # This is an SQS message relayed by the parent Lambda function.
        #
        # Extract some variables from the event dictionary.  See
        # https://docs.aws.amazon.com/AmazonS3/latest/dev/notification-content-structure.html
        # for details on the event structure corresponding to objects created in an
        # S3 bucket.
        receipt_handle = event['ReceiptHandle']
        body = json.loads(event['Body'])
        for record in body['Records']:
            bucket = record['s3']['bucket']['arn']
            key = record['s3']['object']['key']

            # Process the DMARC aggregate reports
            s3.do_it(schema, DOMAINS, REPORTS, elasticsearch, es_region,
                     token, bucket, key, DELETE)
