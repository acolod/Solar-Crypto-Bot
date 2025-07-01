import requests
from pydantic import BaseModel
from typing import Optional
from .config import config
import datetime
import boto3
import uuid


class S3Client:
    def __init__(self):
        self.s3_client_keys = config.s3_client_keys()
        self.api_url = self.s3_client_keys["api_url"]
        self.org_id = self.s3_client_keys["org_id"]
        self.project_id = self.s3_client_keys["project_id"]
        self.api_key = self.s3_client_keys["api_key"]
        self.aws_region = self.s3_client_keys["aws_region"]
        self.aws_bucket_name = self.s3_client_keys["aws_bucket_name"]
        self.expiration = None
        self.s3_client = None

    def get_base_path(self) -> str:
        return f"{self.org_id}/{self.project_id}"

    def refresh_client_if_expired(self):
        if (
            self.s3_client is not None
            and self.expiration is not None
            and self.expiration > datetime.datetime.now(datetime.timezone.utc)
        ):
            return
        response = requests.post(
            f"{self.api_url}/aws/get-s3-credentials",
            json={"orgId": self.org_id, "projectId": self.project_id},
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        if response.status_code != 200:
            raise Exception("Failed to refresh credentials")
        credentials = response.json()
        client = boto3.client(
            "s3",
            aws_access_key_id=credentials["accessKeyId"],
            aws_secret_access_key=credentials["secretAccessKey"],
            aws_session_token=credentials["sessionToken"],
            region_name=self.aws_region,
            config=boto3.session.Config(signature_version="s3v4"),
        )
        self.expiration = datetime.datetime.fromisoformat(
            credentials["expiration"].replace("Z", "+00:00")
        )
        self.s3_client = client


s3_client = None


class MediaFile(BaseModel):
    size: int
    mime_type: str
    bytes: bytes


def get_client():
    global s3_client
    if s3_client is None:
        s3_client = S3Client()
    return s3_client


def save_to_bucket(media_file: MediaFile, file_path: Optional[str] = None):
    client = get_client()
    client.refresh_client_if_expired()
    if file_path is None:
        file_path = f"{uuid.uuid4()}.{media_file.mime_type.split('/')[-1]}"
    full_path = f"{client.get_base_path()}/{file_path}"
    client.s3_client.put_object(
        Bucket=client.aws_bucket_name,
        Key=full_path,
        Body=media_file.bytes,
    )
    return full_path


def delete_from_bucket(path: str):
    client = get_client()
    client.refresh_client_if_expired()
    client.s3_client.delete_object(
        Bucket=client.aws_bucket_name,
        Key=path,
    )


def get_from_bucket(path: str) -> MediaFile:
    client = get_client()
    client.refresh_client_if_expired()

    base_path = client.get_base_path()
    full_path = path if path.startswith(f"{base_path}/") else f"{base_path}/{path}"

    response = client.s3_client.get_object(
        Bucket=client.aws_bucket_name,
        Key=full_path,
    )
    return MediaFile(
        size=response["ContentLength"],
        mime_type=response["ContentType"],
        bytes=response["Body"].read(),
    )


def generate_presigned_url(path: str, expires_in: int = 3600) -> str:
    client = get_client()
    client.refresh_client_if_expired()
    return client.s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": client.aws_bucket_name, "Key": path},
        ExpiresIn=expires_in,
    )
