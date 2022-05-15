#!/usr/bin/env python3
""" Manages SSM Parameters in bulk.

        For usage type: ssm-param.py -h/--help
        For sub-command help: ssm-param.py create|get|delete -h/--help

   By Carlos Bustillo <https://linkedin.com/in/carlosbustillordguez/>
"""
import argparse
import json
import os
import sys
import textwrap

import boto3
from botocore.exceptions import ProfileNotFound


def init_aws_clients(options):
    """ Initialize the AWS clients.

        Args:
            args: the script options.
    """
    # AWS Profile to perform the operations
    aws_profile = options.profile
    aws_region_arg = options.region

    # Global variables
    global ssm
    global aws_region

    # Configured the session for the boto client
    if aws_profile and aws_region_arg:
        try:
            session = boto3.Session(
                profile_name=aws_profile,
                region_name=aws_region_arg,
            )
        except ProfileNotFound as e:
            print(f"{sys.argv[0]} error: " + str(e))
            sys.exit(1)
    elif aws_profile:
        try:
            session = boto3.Session(profile_name=aws_profile)
        except ProfileNotFound as e:
            print(f"{sys.argv[0]} error: " + str(e))
            sys.exit(1)
    elif aws_region_arg:
        session = boto3.Session(region_name=aws_region_arg)
        if aws_region_arg not in session.get_available_regions('ssm'):
            print(f"{sys.argv[0]} error: the specified region {aws_region_arg} is not a valid AWS region")
            sys.exit(1)
    else:
        session = boto3.Session()

    # Create the SSM client
    ssm = session.client('ssm')

    # Get the AWS region for the current session
    aws_region = session.region_name


def create_ssm_parameter(options):
    """ Create the SSM Parameter Store.

        Args:
            args: the script options.
    """
    vars_file = options.file
    ssm_param_type = options.type

    # Remove trailing slash if exists
    ssm_param_path = options.path.rstrip('/')

    # Flag to check if al least one parameter was created
    at_least_one_added = False

    # Check if the vars file exists
    if vars_file and not os.path.isfile(vars_file):
        print(f"The '{vars_file}' does not exists!!!")
        sys.exit(1)

    # Parse env vars
    with open(vars_file) as file:
        for line in file:
            var_name, var_value = line.partition("=")[::2]

            if var_name and var_value:
                # Remove any space and quote (") at the start and the end of the string
                var_name = var_name.strip().strip('"')
                var_value = var_value.strip().strip('"')

                # Check the parameter status on SSM
                check_param_status = check_parameter_in_ssm(ssm_param_path + '/' + var_name, var_value)

                if not check_param_status["found"] and not check_param_status["update"]:
                    # Add a new parameter
                    ssm.put_parameter(
                        Name=ssm_param_path + '/' + var_name,
                        Value=var_value,
                        Type=ssm_param_type,
                        Overwrite=True,
                        Tier='Standard',
                        DataType='text',
                    )

                    print(f"==> Added the parameter '{ssm_param_path}/{var_name}'\n")
                    at_least_one_added = True
                elif check_param_status["found"] and not check_param_status["update"]:
                    print(f"==> No action required. The parameter '{ssm_param_path}/{var_name}' value is updated.\n")
                    at_least_one_added = True
                else:
                    # Update the value of an existing parameter
                    ssm.put_parameter(
                        Name=ssm_param_path + '/' + var_name,
                        Value=var_value,
                        Type=ssm_param_type,
                        Overwrite=True,
                        Tier='Standard',
                        DataType='text',
                    )

                    print(f"==> Updated the parameter '{ssm_param_path}/{var_name}' with a new value.\n")
                    at_least_one_added = True

    if not at_least_one_added:
        print("No detected parameters in the specified file!!!")
        print("The expected format in the file is 'VAR_NAME=foo' or 'VAR_NAME = foo'")


def check_parameter_in_ssm(ssm_param_full_path, para_value):
    """ Check if a parameter already exists and the given value is newer than the parameter's value on SSM.
        The function will return a dict with the following meaning:
            {"found": False, "update": False} - The parameter does not exist yet, we need to add it
            {"found": True, "update": False}  - The parameter exists, we don't need to update its value
            {"found": True, "update": True}   - The parameter exists, we need to update its value

        Args:
            ssm_param_full_path: the SSM parameter full path
            value: the local value of the SSM parameter
    """

    try:
        ssm_param = ssm.get_parameter(
            Name=ssm_param_full_path,
            WithDecryption=True,
        )["Parameter"]
    except ssm.exceptions.ParameterNotFound:
        # The parameter does not exist yet, we need to add it
        return {"found": False, "update": False}
    else:
        if ssm_param["Value"] == para_value:
            # The parameter exists, we don't need to update its value
            return {"found": True, "update": False}
        else:
            # The parameter exists, we need to update its value
            return {"found": True, "update": True}


def get_ssm_parameter(options):
    """ Get the SSM parameters in a specific hierarchy.

        Args:
            args: the script options.
    """

    # Remove trailing slash for the path if exists
    ssm_param_path = options.path.rstrip('/')

    # Get the output type from the options
    outputType = options.output

    # Create a reusable Paginator
    paginator = ssm.get_paginator('get_parameters_by_path')

    # Disable the parameter value decryption when output type is 'ecs'
    if outputType == "ecs":
        decryption = False
    else:
        decryption = True

    # Create a PageIterator from the Paginator
    response_iterator = paginator.paginate(
        Path=ssm_param_path,
        Recursive=True,
        WithDecryption=decryption,
    )

    ssmParamsList = []

    # Get each page from the PageIterator
    for page in response_iterator:
        for parameter in page['Parameters']:
            if outputType == "ecs":
                # Store the parameter name and its ARN in a valid format for ECS secrets in the task definition
                ssmParamsList.append(dict(name=os.path.basename(parameter['Name']), valueFrom=parameter['ARN']))
            else:
                # Store the parameter name and its value in the format NAME=VALUE
                ssmParamsList.append(os.path.basename(parameter['Name']) + '=' + parameter['Value'])

    if ssmParamsList and outputType == "ecs":
        print("==> Add to the 'containerDefinitions[*].secrets' in your task definition: ")
        print(json.dumps(ssmParamsList, indent=2))
    elif ssmParamsList and outputType == "text":
        print(f"==> Parameters in format SHORT_NAME=VALUE. The '{ssm_param_path}' path has been removed from the parameter name!\n")
        for line in ssmParamsList:
            print(line)
    else:
        print(f"No parameters found under '{ssm_param_path}'!!!")


def delete_ssm_parameter(options):
    """ Delete the SSM parameters in a specific hierarchy.

        Args:
            args: the script options.
    """

    # Remove trailing slash if exists
    ssm_param_path = options.path.rstrip('/')

    # Get all parameters in a hierarchy
    response = ssm.get_parameters_by_path(
        Path=ssm_param_path,
        Recursive=True,
        WithDecryption=False,
    )

    if response['Parameters']:
        # Parameters name list
        ssmParamsList = [parameter['Name'] for parameter in response['Parameters']]

        # Remove all parameters in the list
        response = ssm.delete_parameters(
            Names=ssmParamsList,
        )

        print(f"==> Removed all parameters under '{ssm_param_path}'")
    else:
        print(f"No parameters found under '{ssm_param_path}'!!!")


def parse_options(args=sys.argv[1:]):
    """ Parse the script options.

        Args:
            args: the script options.
    """

    # Create the top-level parser
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Manage SSM Parameters",
        epilog=textwrap.dedent(f'''\
            Usage samples:
            --------------
                Create a bulk of SSM parameters in a specific path (hierarchy):
                    {sys.argv[0]} create -p <SSM_PARAM_PATH> -t <String|StringList|SecureString> -f variables.txt

                Get all paremeters in an specific path (hierarchy):
                    {sys.argv[0]} get -p <SSM_PARAM_PATH>

                Delete all paremeters in an specific path (hierarchy):
                    {sys.argv[0]} delete -p <SSM_PARAM_PATH>
            '''),
    )

    # Create a subparser for the sub-commands
    subparsers = parser.add_subparsers(
        help="-f/--help to see the available options",
        dest="subcommand",
        title="available subcommands",
    )

    # Global arguments
    parser.add_argument("-p", "--profile", help="a valid AWS profile name to perform the tasks")
    parser.add_argument("-r", "--region", help="a valid AWS region to perform the tasks")

    # Create the parser for the "create" sub-command
    parser_create = subparsers.add_parser("create", help="create the parameters from a file")
    parser_create.add_argument("-f", "--file", required=True, help="the file with the env vars to add to")
    parser_create.add_argument(
        "-t", "--type", required=True,
        choices=['String', 'StringList', 'SecureString'],
        help="the SSM parameter type, choose one of the valid choices",
    )
    parser_create.add_argument("-p", "--path", required=True, help="the path to create the parameters")
    parser_create.set_defaults(func=create_ssm_parameter)

    # Create the parser for the "get" sub-command
    parser_get = subparsers.add_parser("get", help="get the parameters in a specific hierarchy")
    parser_get.add_argument("-p", "--path", required=True, help="the path to get the parameters")
    parser_get.add_argument(
        "-o", "--output", default="text", choices=['ecs', 'text'],
        help="the output format type, choose one of the valid choices",
    )
    parser_get.set_defaults(func=get_ssm_parameter)

    # Create the parser for the "delete" sub-command
    parser_delete = subparsers.add_parser("delete", help="delete the parameters in a specific hierarchy")
    parser_delete.add_argument("-p", "--path", required=True, help="the path to delete all parameters")
    parser_delete.set_defaults(func=delete_ssm_parameter)

    # Print usage and exit if not arguments are supplied
    if not args:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Parse the args
    options = parser.parse_args(args)

    # Return the parsed args
    return options


def main():
    """ Main function.

        Args:
          None.
    """
    # Parse the args
    options = parse_options(sys.argv[1:])

    # Initialize the AWS clients
    init_aws_clients(options)

    # Select the script subcommand by calling whatever function was selected
    options.func(options)  # call the function assigned to the variable func


if __name__ == "__main__":
    main()
