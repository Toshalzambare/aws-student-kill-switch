"""
AWS Nuclear Button — Local SQS Worker (Secondary Deep Cleanup)
===============================================================
This script runs on your local machine (laptop) and continuously polls
an Amazon SQS queue for budget alert messages.

Lambda has ALREADY fired as the immediate first responder by this point.
This worker provides a deeper cleanup using aws-nuke to catch the
remaining 200+ AWS services that Lambda doesn’t cover.

When a message arrives:
  1. It runs aws-nuke in --no-dry-run mode for complete account cleanup
  2. On success, it deletes the message from SQS
  3. If your laptop is offline, the message simply expires — Lambda
     already handled the critical cost-generating services

Prerequisites:
  - AWS CLI configured with proper credentials
  - aws-nuke installed (https://github.com/rebuy-de/aws-nuke)
  - boto3 installed (pip install boto3)

Usage:
  python sqs_worker.py                    # Normal mode
  python sqs_worker.py --dry-run          # Preview mode (no actual deletion)
  python sqs_worker.py --test             # Process one message and exit
"""

import boto3
import subprocess
import sys
import time
import json
import signal
import logging
import argparse
import os
from datetime import datetime

# ---------- Configuration ----------
# IMPORTANT: Replace these with your actual values!
SQS_QUEUE_URL = "https://sqs.ap-south-1.amazonaws.com/YOUR_ACCOUNT_ID/kill-switch-queue"
AWS_REGION = "ap-south-1"

# Path to the aws-nuke binary on your machine
# Windows: "C:\\path\\to\\aws-nuke.exe"
# macOS/Linux: "/usr/local/bin/aws-nuke"
AWS_NUKE_PATH = "aws-nuke"

# Determine the base path (handles both running as a script and as a compiled PyInstaller .exe)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to the aws-nuke config file
NUKE_CONFIG_PATH = os.path.join(BASE_DIR, "nuke-config.yaml")

# Polling interval in seconds (how often to check for messages)
POLL_INTERVAL = 10

# SQS long-polling wait time (max 20 seconds — reduces API calls)
SQS_WAIT_TIME = 20

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(BASE_DIR, "worker.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger("sqs-worker")


class GracefulShutdown:
    """Handle Ctrl+C gracefully."""
    def __init__(self):
        self.should_stop = False
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, signum, frame):
        logger.info("🛑 Shutdown signal received. Finishing current task...")
        self.should_stop = True


def run_aws_nuke(dry_run=False):
    """
    Execute aws-nuke to wipe the AWS account.
    
    Returns:
        bool: True if aws-nuke completed successfully, False otherwise.
    """
    cmd = [
        AWS_NUKE_PATH,
        "-c", NUKE_CONFIG_PATH,
        "--force",              # Skip the initial prompt
        "--no-dry-run" if not dry_run else "--dry-run",
    ]

    logger.info(f"🔥 Executing: {' '.join(cmd)}")

    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10-minute timeout
        )

        # Log output
        if process.stdout:
            for line in process.stdout.strip().split("\n"):
                logger.info(f"  [aws-nuke] {line}")
        if process.stderr:
            for line in process.stderr.strip().split("\n"):
                logger.warning(f"  [aws-nuke stderr] {line}")

        if process.returncode == 0:
            logger.info("✅ aws-nuke completed successfully!")
            return True
        else:
            logger.error(f"❌ aws-nuke exited with code {process.returncode}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("❌ aws-nuke timed out after 10 minutes!")
        return False
    except FileNotFoundError:
        logger.error(f"❌ aws-nuke not found at: {AWS_NUKE_PATH}")
        logger.error("   Install it from: https://github.com/rebuy-de/aws-nuke")
        return False
    except Exception as e:
        logger.error(f"❌ Error running aws-nuke: {str(e)}")
        return False


def process_message(message, dry_run=False):
    """
    Process a single SQS message (budget alert).
    
    Args:
        message: The SQS message dict.
        dry_run: If True, run aws-nuke in preview mode.
        
    Returns:
        bool: True if the message was processed successfully.
    """
    message_id = message["MessageId"]
    body = message.get("Body", "")

    logger.info(f"📨 Received message: {message_id}")
    logger.info(f"   Body: {body[:200]}")

    # Parse the SNS notification wrapper if present
    try:
        sns_wrapper = json.loads(body)
        if "Message" in sns_wrapper:
            logger.info(f"   SNS Subject: {sns_wrapper.get('Subject', 'N/A')}")
            logger.info(f"   SNS Message: {sns_wrapper['Message'][:200]}")
    except (json.JSONDecodeError, TypeError):
        pass

    logger.info("=" * 50)
    logger.info("🚨 BUDGET ALERT DETECTED!")
    logger.info(f"   Time: {datetime.now().isoformat()}")
    logger.info(f"   Mode: {'DRY-RUN (preview only)' if dry_run else '🔴 LIVE — DELETING RESOURCES'}")
    logger.info("=" * 50)

    # Execute aws-nuke
    success = run_aws_nuke(dry_run=dry_run)

    return success


def poll_sqs(sqs_client, dry_run=False, single_run=False):
    """
    Continuously poll the SQS queue for messages.
    
    Args:
        sqs_client: boto3 SQS client.
        dry_run: If True, run aws-nuke in preview mode.
        single_run: If True, process one message and exit.
    """
    shutdown = GracefulShutdown()

    logger.info("=" * 60)
    logger.info("🛡️  AWS Nuclear Button — Local Worker")
    logger.info(f"   Queue: {SQS_QUEUE_URL}")
    logger.info(f"   Mode:  {'DRY-RUN' if dry_run else '🔴 LIVE'}")
    logger.info(f"   Polling every: {POLL_INTERVAL}s (long-poll: {SQS_WAIT_TIME}s)")
    logger.info("   Press Ctrl+C to stop gracefully")
    logger.info("=" * 60)

    while not shutdown.should_stop:
        try:
            response = sqs_client.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=SQS_WAIT_TIME,
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])

            if not messages:
                if not single_run:
                    logger.debug("No messages. Waiting...")
                    continue
                else:
                    logger.info("No messages in queue. Exiting test mode.")
                    return

            for message in messages:
                success = process_message(message, dry_run=dry_run)

                if success:
                    # Delete the message from the queue
                    sqs_client.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=message["ReceiptHandle"]
                    )
                    logger.info(f"✅ Message {message['MessageId']} deleted from queue.")
                else:
                    logger.warning(
                        f"⚠️ Message {message['MessageId']} NOT deleted. "
                        "It will return to the queue for retry. "
                        "Lambda already handled the critical services."
                    )

                if single_run:
                    logger.info("Test mode: processed one message. Exiting.")
                    return

        except Exception as e:
            logger.error(f"❌ Error polling SQS: {str(e)}")
            time.sleep(POLL_INTERVAL)

    logger.info("👋 Worker shut down gracefully.")


def main():
    parser = argparse.ArgumentParser(
        description="AWS Nuclear Button — Local SQS Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sqs_worker.py                 Start polling in LIVE mode
  python sqs_worker.py --dry-run       Start polling in preview mode
  python sqs_worker.py --test          Process one message and exit
  python sqs_worker.py --test --dry-run  Test with preview mode
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run aws-nuke in preview mode (no actual deletions)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Process a single message and exit"
    )

    args = parser.parse_args()

    # Validate configuration
    if "YOUR_ACCOUNT_ID" in SQS_QUEUE_URL:
        logger.error("❌ You must update SQS_QUEUE_URL with your actual queue URL!")
        logger.error("   Edit the configuration section at the top of this file.")
        sys.exit(1)

    if not os.path.exists(NUKE_CONFIG_PATH):
        logger.error(f"❌ aws-nuke config not found at: {NUKE_CONFIG_PATH}")
        logger.error("   Make sure nuke-config.yaml exists in the same directory.")
        sys.exit(1)

    # Initialize SQS client
    sqs = boto3.client("sqs", region_name=AWS_REGION)

    # Start polling
    poll_sqs(sqs, dry_run=args.dry_run, single_run=args.test)


if __name__ == "__main__":
    main()
