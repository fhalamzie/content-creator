"""S3/B2 uploader for image storage.

Uploads base64-encoded images to Backblaze B2 (S3-compatible)
and returns public URLs for use in Notion.
"""

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class S3Uploader:
    """Upload images to S3-compatible storage (Backblaze B2)."""

    def __init__(self):
        """Initialize S3 client with B2 credentials."""
        self.endpoint = os.getenv('B2_ENDPOINT')
        self.key_id = os.getenv('B2_KEY_ID')
        self.app_key = os.getenv('B2_APPLICATION_KEY')
        self.bucket_name = os.getenv('B2_BUCKET_NAME')

        # Validate credentials
        if not all([self.endpoint, self.key_id, self.app_key, self.bucket_name]):
            raise ValueError(
                "Missing B2 credentials. Set B2_ENDPOINT, B2_KEY_ID, "
                "B2_APPLICATION_KEY, B2_BUCKET_NAME in .env"
            )

        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{self.endpoint}',
            aws_access_key_id=self.key_id,
            aws_secret_access_key=self.app_key,
            region_name='eu-central-003'  # B2 region
        )

        logger.info(f"S3Uploader initialized with bucket: {self.bucket_name}")

    def upload_base64_image(
        self,
        base64_data: str,
        filename: Optional[str] = None,
        content_type: str = 'image/jpeg'
    ) -> str:
        """
        Upload a base64-encoded image to B2, return public URL.

        Args:
            base64_data: Base64-encoded image data (with or without data:image prefix)
            filename: Optional custom filename (auto-generated if None)
            content_type: MIME type (default: image/jpeg)

        Returns:
            Public URL to the uploaded image

        Raises:
            ValueError: If base64 data is invalid
            ClientError: If upload fails
        """
        # Remove data URI prefix if present (data:image/jpeg;base64,...)
        if base64_data.startswith('data:'):
            base64_data = base64_data.split(',', 1)[1]

        # Decode base64 to bytes
        try:
            image_bytes = base64.b64decode(base64_data)
        except Exception as e:
            raise ValueError(f"Invalid base64 data: {e}")

        # Generate filename if not provided (use content hash)
        if not filename:
            content_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
            extension = self._get_extension_from_content_type(content_type)
            filename = f"images/{content_hash}{extension}"

        # Upload to B2
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=image_bytes,
                ContentType=content_type,
                CacheControl='public, max-age=31536000'  # Cache for 1 year
            )

            # Generate public URL
            public_url = f"https://{self.endpoint}/{self.bucket_name}/{filename}"

            logger.info(f"Uploaded image to B2: {filename} ({len(image_bytes)} bytes)")
            return public_url

        except ClientError as e:
            logger.error(f"Failed to upload to B2: {e}")
            raise

    def upload_local_file(
        self,
        file_path: str,
        object_name: Optional[str] = None
    ) -> str:
        """
        Upload a local file to B2, return public URL.

        Args:
            file_path: Path to local file
            object_name: S3 object name (uses filename if None)

        Returns:
            Public URL to the uploaded file

        Raises:
            FileNotFoundError: If file doesn't exist
            ClientError: If upload fails
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Use filename as object name if not provided
        if not object_name:
            object_name = f"images/{path.name}"

        # Detect content type
        content_type = self._get_content_type(path)

        # Upload file
        try:
            self.s3_client.upload_file(
                str(path),
                self.bucket_name,
                object_name,
                ExtraArgs={
                    'ContentType': content_type,
                    'CacheControl': 'public, max-age=31536000'
                }
            )

            # Generate public URL
            public_url = f"https://{self.endpoint}/{self.bucket_name}/{object_name}"

            logger.info(f"Uploaded file to B2: {object_name}")
            return public_url

        except ClientError as e:
            logger.error(f"Failed to upload file to B2: {e}")
            raise

    def _get_content_type(self, path: Path) -> str:
        """Detect content type from file extension."""
        extension = path.suffix.lower()
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml'
        }
        return content_types.get(extension, 'application/octet-stream')

    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content type."""
        extensions = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg'
        }
        return extensions.get(content_type, '.jpg')


# Singleton instance
_uploader: Optional[S3Uploader] = None


def get_s3_uploader() -> S3Uploader:
    """Get or create S3Uploader singleton instance."""
    global _uploader
    if _uploader is None:
        _uploader = S3Uploader()
    return _uploader
