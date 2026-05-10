"""phrasaurus — AWS Lambda backend for the phrase-to-phrase thesaurus.

The package is organised around a single responsibility per module:

- ``config``         Runtime configuration derived from environment variables.
- ``bedrock_client`` Pure prompt-building + Amazon Bedrock Converse API call.
- ``handler``        AWS Lambda entry point — request parsing, validation,
                     orchestration, response shaping, error handling.

Keeping I/O (AWS, Bedrock, Lambda event shape) isolated from the prompt
logic lets us test the business logic without network access. The function
authenticates to Bedrock via the Lambda execution role — there are no
long-lived credentials to store or rotate.
"""

__version__ = "0.3.0"
