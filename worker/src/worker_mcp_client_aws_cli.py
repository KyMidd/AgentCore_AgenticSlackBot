import os
import shutil
from mcp import stdio_client, StdioServerParameters
from strands.tools.mcp.mcp_client import MCPClient

TOOLS_PREFIX = "aws"


def build_aws_cli_mcp_client(
    aws_region="us-east-1",
):
    """Build AWS CLI MCP client."""

    opt_aws_cli_mcp_dir = "/opt/aws-cli-mcp-server"

    # Create working directory in /tmp for runtime files
    os.makedirs("/tmp/aws-mcp-working", exist_ok=True)
    os.makedirs("/tmp/.aws", exist_ok=True)

    # Copy AWS config file with pre-configured profiles to /tmp
    shutil.copy("/opt/aws_config", "/tmp/.aws/config")

    # Build environment variables for AWS CLI MCP
    env = {
        "HOME": "/tmp",  # Lambda not writeable except /tmp
        "AWS_API_MCP_WORKING_DIR": "/tmp/aws-mcp-working",
        "AWS_REGION": aws_region,
        "AWS_CONFIG_FILE": "/tmp/.aws/config",
        "AWS_SDK_LOAD_CONFIG": "1",
        # Pass through execution role credentials
        "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_SESSION_TOKEN": os.environ.get("AWS_SESSION_TOKEN", ""),
    }

    # Create AWS MCP client
    aws_cli_mcp_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                cwd="/tmp/aws-mcp-working",
                command=f"{opt_aws_cli_mcp_dir}/.venv/bin/awslabs.aws-api-mcp-server",
                env=env,
            )
        ),
        prefix=TOOLS_PREFIX,
    )

    return aws_cli_mcp_client
