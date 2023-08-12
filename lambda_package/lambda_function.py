mport json
import boto3
import openai
from botocore.exceptions import ClientError

model = "gpt-3.5-turbo-0613"
system_content = 'You function as a phrase thesaurus. Upon receiving a word, words, or a phrase, your response will exclusively consist a single synonymous words or phrases. No additional text, context, or explanations should be provided. Your output will strictly adhere to the principle of phrase synonymy. '

messages = [
    {"role": "system", "content": system_content},
    {"role" : "user", "content" : "Give me a word or phrase that reflects the inner struggle of man kind but on a more acedemic level"},
    {"role" : "assistant", "content" : "existential crisis"},
    {"role" : "user", "content" : "a lot of pain due to heat"},
    {"role" : "assistant", "content" : "Intense discomfort caused by high temperature"},
    {"role" : "user", "content" : "I helped a patient in need of surgery"},
    {"role" : "assistant", "content" : "Assisted in a critical surgical intervention"},
    {"role" : "user", "content" : "Assistant, what's the tallest mountain in the world"},
    {"role" : "assistant", "content" : "Which peak is the highest?"}
]

def handle(user_message, organization, api_key):
    openai.organization = organization
    openai.api_key = api_key
    messages.append({"role" : "user", "content" : user_message})
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        max_tokens=50
    )
    response_message = response["choices"][0]["message"]
    return response_message['content']


def lambda_handler(event, context):
    # TODO implement
    
    print(event)
    print("***")
    organization, api_key = get_secret()
    out = handle("green moneky", organization, api_key)
    print(context)
    
    return {
        'statusCode': 200,
        'body': json.dumps('')
    }


def get_secret():

    secret_name = "prod/openai"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e
        
    secret = json.loads(get_secret_value_response['SecretString'])
    # Decrypts secret using the associated KMS key.
    organization = secret["ORGANIZATION"]
    api_key = secret['API_KEY']
    return api_key, organization
    


