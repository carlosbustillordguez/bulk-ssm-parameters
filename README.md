# Manages SSM Parameters in bulk

Allows to create, get and delete SSM parameters in a specific hierarchy.

## Requirements

- Python version 3+.
- For Python requirements see the `requirements.txt` file.
- The following permission are required:
  - `ssm:PutParameter`
  - `ssm:GetParameter`
  - `ssm:GetParametersByPath`
  - `ssm:DeleteParameters`
  - `kms:Decrypt`

The following policy must be added to the IAM user before execute the script, with a user with high privileges:

1- Add the IAM Policy:

```sh
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)

cat <<EOF > ssm-param-policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCreateGetDeleteSSMParams",
            "Effect": "Allow",
            "Action": [
                "ssm:PutParameter",
                "ssm:GetParameter"
                "ssm:GetParametersByPath",
                "ssm:DeleteParameters",
                "kms:Decrypt"
            ],
            "Resource": "arn:aws:ssm:*:${ACCOUNT_ID}:parameter/*"
        }
    ]
}
EOF

IAM_POLICY_ARN=$(aws iam create-policy --policy-name BulkSSSMParametersScript \
  --policy-document file://ssm-param-policy.json \
  --description "Add required permissions to run the ssm-param script" \
  --query 'Policy.Arn' --output text)
```

2- Add the IAM policy to the user to execute the `ssm-param` script:

```sh
aws iam attach-user-policy --policy-arn "$IAM_POLICY_ARN" --user-name <YOUR_IAM_USER_NAME>
```

3- Be sure to executes the `ssm-param` script using your *<YOUR_IAM_USER_NAME>*.

## How to use the script

1- Install the Python's requirements:

```sh
pip3 install -r requirements.txt
```

2- Select an operation to accomplish:

To create a bulk of SSM parameters in a specific path (hierarchy) `/infra/apps/myapp` using the AWS profile **my-aws-profile**:

```sh
ssm-param.py --profile my-aws-profile create --path /infra/apps/myapp --type SecureString --file variables.txt
```

**NOTE:** for this task you must have a file with the environment variables to add, one per line with the format `VAR_NAME=foo` or `VAR_NAME = foo`.

To get all paremeters in an specific path (hierarchy) `/infra/apps/myapp` using the AWS profile **my-aws-profile**:

```sh
ssm-param.py --profile my-aws-profile get --path /infra/apps/myapp
```

To delete all paremeters in an specific path (hierarchy) `/infra/apps/myapp` using the AWS profile **my-aws-profile**:

```sh
ssm-param.py --profile my-aws-profile delete --path /infra/apps/myapp
```

**NOTES**:

- You can set the `AWS_PROFILE` or `AWS_DEFAULT_PROFILE` before execute the `ssm-param.py` tool and ommit the optional argument `-p/--profile`.
- The subcommand `get` has the `-o/--output` flag to specify the output type. Valid values are `ecs` or `text`. Is not specified, the default value (`text`) is assumed.
- The `text` output type, print all parameters name and its value under the specified path (hierarchy). This kind of output can be useful if you want to export those values in the format `SHORT_NAME=VALUE`. Where `SHORT_NAME` if the value(s) found under the path (hierarchy) specified in the command line.
- The `ecs` output will be a JSON with the expected format for *secrets* in the a [ECS task definition](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data-parameters.html#secrets-envvar-parameters).

## License

MIT

## Author Information

By: [Carlos M Bustillo Rdguez](https://linkedin.com/in/carlosbustillordguez/)
