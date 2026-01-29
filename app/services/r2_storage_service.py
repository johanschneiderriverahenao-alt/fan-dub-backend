"""
Cloudflare R2 Storage Service.
Handles file upload, download, and deletion operations using boto3.
R2 is compatible with AWS S3 API.
"""
# pylint: disable=W0718

import io
import unicodedata
from typing import Optional, BinaryIO
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from fastapi import UploadFile

from app.config.settings import settings
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class R2StorageService:
    """Service for interacting with Cloudflare R2 Storage."""

    def __init__(self):
        """Initialize R2 client with credentials from settings."""
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name='auto'  # R2 uses 'auto' for region
            )
            self.bucket_name = settings.r2_bucket_name
            self.public_url = settings.r2_public_url
            log_info(logger, "R2 Storage client initialized successfully")
        except Exception as e:
            log_error(logger, "Failed to initialize R2 client", {"error": str(e)})
            raise RuntimeError(f"R2 initialization failed: {str(e)}") from e

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to contain only ASCII characters.
        Converts accented characters to their ASCII equivalents.

        Args:
            filename: Original filename

        Returns:
            ASCII-safe filename
        """
        # Normalize unicode characters (NFD = decomposed form)
        # This separates accents from base characters
        normalized = unicodedata.normalize('NFD', filename)
        # Filter out combining characters (accents) and keep only ASCII
        ascii_name = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        # Encode to ASCII, replacing any remaining non-ASCII chars
        return ascii_name.encode('ascii', 'ignore').decode('ascii')

    def _generate_file_key(self, folder: str, filename: str) -> str:
        """
        Generate a unique file key for storage.

        Args:
            folder: Folder/prefix for organizing files
            filename: Original filename

        Returns:
            Unique file key with timestamp
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Clean filename and add timestamp
        clean_name = filename.replace(" ", "_")
        return f"{folder}/{timestamp}_{clean_name}"

    async def upload_file(
        self,
        file: UploadFile,
        folder: str = "videos",
        custom_filename: Optional[str] = None
    ) -> dict:
        """
        Upload a file to R2 storage.

        Args:
            file: FastAPI UploadFile object
            folder: Folder/prefix for organizing files (default: "videos")
            custom_filename: Optional custom filename (uses original if not provided)

        Returns:
            Dict with file_key, file_url, and metadata

        Raises:
            RuntimeError: If upload fails
        """
        try:
            filename = custom_filename or file.filename
            file_key = self._generate_file_key(folder, filename)

            file_content = await file.read()

            content_type = file.content_type or "application/octet-stream"

            # Sanitize filename for metadata (S3 only accepts ASCII)
            safe_filename = self._sanitize_filename(file.filename)

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    "original_filename": safe_filename,
                    "upload_date": datetime.utcnow().isoformat()
                }
            )

            file_url = self._generate_public_url(file_key)

            log_info(logger, f"File uploaded successfully: {file_key}")

            return {
                "file_key": file_key,
                "file_url": file_url,
                "original_filename": file.filename,
                "content_type": content_type,
                "size": len(file_content)
            }

        except (ClientError, BotoCoreError) as e:
            log_error(logger, "R2 upload failed", {"error": str(e), "filename": file.filename})
            raise RuntimeError(f"Failed to upload file to R2: {str(e)}") from e
        except Exception as e:
            log_error(logger, "Unexpected error during upload", {"error": str(e)})
            raise RuntimeError(f"Unexpected upload error: {str(e)}") from e

    def _generate_public_url(self, file_key: str) -> str:
        """
        Generate public URL for a file.

        Args:
            file_key: The file key in R2

        Returns:
            Public URL for the file
        """
        if self.public_url:
            return f"{self.public_url}/{file_key}"
        base_url = settings.r2_endpoint_url.replace('https://', '')
        return f"https://{base_url}/{self.bucket_name}/{file_key}"

    async def get_file(self, file_key: str) -> BinaryIO:
        """
        Download a file from R2 storage.

        Args:
            file_key: The file key in R2

        Returns:
            File content as binary stream

        Raises:
            RuntimeError: If download fails
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_key
            )

            file_stream = io.BytesIO(response['Body'].read())
            log_info(logger, f"File retrieved successfully: {file_key}")
            return file_stream

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                log_error(logger, "File not found in R2", {"file_key": file_key})
                raise RuntimeError(f"File not found: {file_key}") from e
            log_error(logger, "R2 download failed", {"error": str(e), "file_key": file_key})
            raise RuntimeError(f"Failed to download file from R2: {str(e)}") from e
        except Exception as e:
            log_error(logger, "Unexpected error during download", {"error": str(e)})
            raise RuntimeError(f"Unexpected download error: {str(e)}") from e

    async def delete_file(self, file_key: str) -> bool:
        """
        Delete a file from R2 storage.

        Args:
            file_key: The file key in R2

        Returns:
            True if deletion successful

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            log_info(logger, f"File deleted successfully: {file_key}")
            return True

        except (ClientError, BotoCoreError) as e:
            log_error(logger, "R2 deletion failed", {"error": str(e), "file_key": file_key})
            raise RuntimeError(f"Failed to delete file from R2: {str(e)}") from e
        except Exception as e:
            log_error(logger, "Unexpected error during deletion", {"error": str(e)})
            raise RuntimeError(f"Unexpected deletion error: {str(e)}") from e

    def get_file_url(self, file_key: str) -> str:
        """
        Get public URL for a file without downloading it.

        Args:
            file_key: The file key in R2

        Returns:
            Public URL for the file
        """
        return self._generate_public_url(file_key)

    async def file_exists(self, file_key: str) -> bool:
        """
        Check if a file exists in R2 storage.

        Args:
            file_key: The file key in R2

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            return True
        except ClientError:
            return False


r2_service = R2StorageService()
